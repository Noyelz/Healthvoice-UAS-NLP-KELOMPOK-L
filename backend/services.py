import asyncio
import os
import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, Transcript, QAEntry, ProcessingStatus
from models_ai import transcribe_audio_safe, generate_answer_safe, get_embedder
from sentence_transformers import util

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "../data/uploads")

async def process_transcription(db: Session, transcript_id: str):
    record = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not record:
        return
    
    try:
        print(f"[{record.filename}] Starting Processing...")
        record.status = ProcessingStatus.PROCESSING
        record.process_start = datetime.datetime.utcnow()
        record.current_step = "Loading Audio Model..."
        db.commit()
        
        medical_prompt = "Transkrip ini adalah rekaman medis wawancara dokter dengan ibu pasien tuberkulosis (TB) anak balita. Gunakan istilah medis yang tepat seperti Isoniazid, Rifampisin, Mantoux, rontgen, berat badan."
        
        record.current_step = "Transcribing (This may take a while)..."
        db.commit()
        
        result = await transcribe_audio_safe(record.file_path, prompt=medical_prompt)
        text_content = result["text"]
        
        record.raw_text = text_content
        record.status = ProcessingStatus.COMPLETED
        record.process_end = datetime.datetime.utcnow()

        
        record.progress = 100
        record.current_step = "Done."
        db.commit()
        print(f"[{record.filename}] Completed.")
        
        print(f"[{record.filename}] Injecting Automated Questions...")
        
        q_file = os.path.join(BASE_DIR, "questions.txt")
        automated_questions = {}
        
        if os.path.exists(q_file):
            with open(q_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "|" in line:
                        parts = line.split("|", 1)
                        if len(parts) == 2:
                            automated_questions[parts[0].strip()] = parts[1].strip()
        else:
             print("Warning: questions.txt not found! No automated questions will be added.")
        
        for label, prompt in automated_questions.items():
            new_qa = QAEntry(
                transcript_id=record.id,
                question=f"{label}: {prompt}",
                status=ProcessingStatus.QUEUED
            )
            db.add(new_qa)
        
        db.commit()
        print(f"[{record.filename}] Automated Questions Queued ({len(automated_questions)} items).")
        
    except Exception as e:
        print(f"[{record.filename}] Error: {str(e)}")
        record.status = ProcessingStatus.ERROR
        record.current_step = f"Error: {str(e)}"
        db.commit()

async def process_qa(db: Session, qa_id: str):
    entry = db.query(QAEntry).filter(QAEntry.id == qa_id).first()
    if not entry:
        return

    try:
        transcript = entry.transcript
        if not transcript or not transcript.raw_text:
            entry.status = ProcessingStatus.ERROR
            entry.answer = "Maaf, transkrip belum selesai atau tidak ditemukan."
            db.commit()
            return
            
        print(f"[QA] Processing: '{entry.question}'")
        entry.status = ProcessingStatus.PROCESSING
        db.commit()
        
        embedder = get_embedder()
        full_text = transcript.raw_text
        

        from nltk.tokenize import sent_tokenize
        sentences = sent_tokenize(full_text)
        
        query_emb = embedder.encode(entry.question, convert_to_tensor=True)
        doc_embs = embedder.encode(sentences, convert_to_tensor=True)
        
        import torch
        
        scores = util.cos_sim(query_emb, doc_embs)[0]
        

        top_k = len(scores)
        top_results = torch.topk(scores, k=top_k)
        
        thresholds_to_try = [0.3, 0.4]
        
        for attempt, current_threshold in enumerate(thresholds_to_try):
            print(f"\n[IR] Retrieval (Attempt {attempt+1}) using Threshold > {current_threshold}")
            
            retrieved_contexts = []
            seen_snippets = set()
            
            for i, (score, idx) in enumerate(zip(top_results.values, top_results.indices)):
                 score_val = score.item()
                 idx_val = idx.item()
                 sentence_text = sentences[idx_val]
    
                 if score_val > current_threshold:

                     cleaned_text = sentence_text.strip().lower()
                     if cleaned_text in seen_snippets:
                         continue
                     seen_snippets.add(cleaned_text)
                     
                     snippet = sentence_text
                     retrieved_contexts.append(snippet)
                     

                     if attempt == 0:
                         text_preview = sentence_text.replace('\n', ' ')
                         print(f"   - Match #{i+1} Score {score_val:.4f}: \"{text_preview[:100]}...\"")
                 else:

                     break
            

            if not retrieved_contexts:
                 context = "Tidak ada informasi relevan ditemukan dalam transkrip."
            else:
                 context = "\n---\n".join(retrieved_contexts)
                 
            entry.context_used = context
            
            try:
                print(f"[LLM] Generating answer with context length: {len(context)} chars...")
                answer = await generate_answer_safe(context, entry.question)
                

                try:

                    
                    def normalize_tokens(text):
                        return [w.lower().strip(",.?!") for w in text.split() if w.strip(",.?!")]

                    ans_tokens = normalize_tokens(answer)
                    ctx_tokens = set(normalize_tokens(context)) 
                    
                    if not ans_tokens:
                        score = 0.0
                    elif answer.strip() in ["-", "Tidak disebutkan", "Tidak ada"]:
                        score = 1.0 
                    else:
                        match_count = sum(1 for w in ans_tokens if w in ctx_tokens)
                        score = match_count / len(ans_tokens)
                    
                    entry.bleu_score = float(score)
                    print(f"[QA] Confidence Score: {score:.4f}")
                except Exception as e:
                    print(f"[QA] Score Calc Error: {e}")
                    entry.bleu_score = 0.0


                entry.answer = answer
                entry.status = ProcessingStatus.COMPLETED
                db.commit()
                print(f"[QA] Completed: '{entry.question}'")
                break
                
            except Exception as e:
                print(f"[QA] LLM Error on Attempt {attempt+1}: {str(e)}")
                
                if attempt == len(thresholds_to_try) - 1:
                    entry.status = ProcessingStatus.ERROR
                    entry.answer = f"Error (Context Limit): {str(e)}"
                    db.commit()
                else:
                    print("Retrying with stricter threshold to reduce context size...")
                    continue

    except Exception as e:
        print(f"[QA] Critical Error: {str(e)}")
        entry.status = ProcessingStatus.ERROR
        entry.answer = f"System Error: {str(e)}"
        db.commit()

async def background_worker():
    print("Background Worker Started.")
    while True:
        db = SessionLocal()
        try:

            qa = db.query(QAEntry).filter(QAEntry.status == ProcessingStatus.QUEUED).first()
            if qa:
                await process_qa(db, qa.id)
                continue 
            
            tx = db.query(Transcript).filter(Transcript.status == ProcessingStatus.QUEUED).first()
            if tx:
                await process_transcription(db, tx.id)
                continue
                
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Worker Loop Error: {e}")
            await asyncio.sleep(1)
        finally:
            db.close()
