import asyncio
import os
import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, Transcript, QAEntry, ProcessingStatus
from models_ai import transcribe_audio_safe, generate_answer_safe, get_embedder
from sentence_transformers import util

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "../data/uploads")

async def process_transcription(db: Session, transcript_id: str):
    """
    Worker function to process a single transcription.
    """
    record = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not record:
        return
    
    try:
        print(f"[{record.filename}] Starting Processing...")
        record.status = ProcessingStatus.PROCESSING
        record.process_start = datetime.datetime.utcnow()
        record.current_step = "Loading Audio Model..."
        db.commit()
        
        # Medical Prompt
        medical_prompt = "Transkrip ini adalah rekaman medis wawancara dokter dengan ibu pasien tuberkulosis (TB) anak balita. Gunakan istilah medis yang tepat seperti Isoniazid, Rifampisin, Mantoux, rontgen, berat badan."
        
        # Run Whisper (Safe Locked)
        record.current_step = "Transcribing (This may take a while)..."
        db.commit()
        
        result = await transcribe_audio_safe(record.file_path, prompt=medical_prompt)
        text_content = result["text"]
        
        # Save Result
        record.raw_text = text_content
        record.status = ProcessingStatus.COMPLETED
        record.process_end = datetime.datetime.utcnow()
        
        # Calculate duration if possible (or from file metadata earlier)
        # record.duration_seconds = ... 
        
        record.progress = 100
        record.current_step = "Done."
        db.commit()
        print(f"[{record.filename}] Completed.")
        
    except Exception as e:
        print(f"[{record.filename}] Error: {str(e)}")
        record.status = ProcessingStatus.ERROR
        record.current_step = f"Error: {str(e)}"
        db.commit()

async def process_qa(db: Session, qa_id: str):
    """
    Worker function to process a single Q&A entry.
    """
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
        
        # 1. Retrieval (IR)
        # We can run this outside the lock because it's CPU based (sentence-transformers)
        # or lightweight enough.
        embedder = get_embedder()
        full_text = transcript.raw_text
        
        # Simple sliding window or split by sentences
        # For robustness, let's just find relevant sentences.
        # Implementation of get_context_window logic from ir2.ipynb
        
        # (Simplified IR for now)
        from nltk.tokenize import sent_tokenize
        sentences = sent_tokenize(full_text)
        
        query_emb = embedder.encode(entry.question, convert_to_tensor=True)
        doc_embs = embedder.encode(sentences, convert_to_tensor=True)
        
        import torch
        
        scores = util.cos_sim(query_emb, doc_embs)[0]
        
        # Get ALL results sorted by score
        # We will filter purely by threshold later
        # Get ALL results sorted by score
        top_k = len(scores)
        top_results = torch.topk(scores, k=top_k)
        
        # Retry Logic: Try with 0.3, if LLM fails (context too long), retry with 0.4
        thresholds_to_try = [0.3, 0.4]
        
        for attempt, current_threshold in enumerate(thresholds_to_try):
            print(f"\n[IR] Retrieval (Attempt {attempt+1}) using Threshold > {current_threshold}")
            
            retrieved_contexts = []
            seen_snippets = set()
            
            for i, (score, idx) in enumerate(zip(top_results.values, top_results.indices)):
                 score_val = score.item()
                 idx_val = idx.item()
                 sentence_text = sentences[idx_val]
    
                 # Filter PURELY by Threshold
                 if score_val > current_threshold:
                     # Check for duplicates
                     cleaned_text = sentence_text.strip().lower()
                     if cleaned_text in seen_snippets:
                         continue
                     seen_snippets.add(cleaned_text)
                     
                     snippet = sentence_text
                     retrieved_contexts.append(snippet)
                     
                     # Optional: Only log on first attempt to avoid spam
                     if attempt == 0:
                         text_preview = sentence_text.replace('\n', ' ')
                         print(f"   - Match #{i+1} Score {score_val:.4f}: \"{text_preview[:100]}...\"")
                 else:
                     # Since results are sorted, once we hit below threshold, we can stop
                     break
            
            # Combine snippets
            if not retrieved_contexts:
                 context = "Tidak ada informasi relevan ditemukan dalam transkrip."
            else:
                 context = "\n---\n".join(retrieved_contexts)
                 
            entry.context_used = context
            
            try:
                # 2. Generation (LLM) - Locked
                print(f"[LLM] Generating answer with context length: {len(context)} chars...")
                answer = await generate_answer_safe(context, entry.question)
                
                # If successful, save and break
                entry.answer = answer
                entry.status = ProcessingStatus.COMPLETED
                db.commit()
                print(f"[QA] Completed: '{entry.question}'")
                break
                
            except Exception as e:
                print(f"[QA] LLM Error on Attempt {attempt+1}: {str(e)}")
                
                # If this was the last attempt, mark as error
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
    """
    Infinite loop to check DB for queued tasks.
    """
    print("Background Worker Started.")
    while True:
        db = SessionLocal()
        try:
            # 1. Check Transcripts
            # We prioritize transcripts? Or Q&A? 
            # Let's prioritize Q&A so user waiting for answer feels fast, 
            # while long transcription runs in background.
            
            # Check Q&A first
            qa = db.query(QAEntry).filter(QAEntry.status == ProcessingStatus.QUEUED).first()
            if qa:
                await process_qa(db, qa.id)
                continue # Immediately check for next task
            
            # Check Transcripts
            tx = db.query(Transcript).filter(Transcript.status == ProcessingStatus.QUEUED).first()
            if tx:
                await process_transcription(db, tx.id)
                continue
                
            # Nothing to do, sleep
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Worker Loop Error: {e}")
            await asyncio.sleep(1)
        finally:
            db.close()
