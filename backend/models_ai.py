import os
print("DEBUG: Starting Imports...", flush=True)
import asyncio
import whisper
print("DEBUG: Imported whisper", flush=True)
import torch
print("DEBUG: Imported torch", flush=True)
from sentence_transformers import SentenceTransformer, util
print("DEBUG: Imported sentence_transformers", flush=True)
from llama_cpp import Llama
print("DEBUG: Imported llama_cpp", flush=True)
from huggingface_hub import hf_hub_download

GPU_LOCK = asyncio.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = r"D:\hf_cache"
os.environ["HF_HOME"] = MODELS_DIR

_whisper_model = None
_embedder_model = None
_llm_model = None

import gc

def unload_whisper():
    global _whisper_model
    if _whisper_model is not None:
        print("Unloading Whisper Model to free VRAM...")
        del _whisper_model
        _whisper_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def unload_llm():
    global _llm_model
    if _llm_model is not None:
        print("Unloading LLM to free VRAM...")
        del _llm_model
        _llm_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def clear_vram():
    print("Cleaning VRAM...")
    unload_whisper()
    unload_llm()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("VRAM Cleaned.")

def get_whisper_model():
    global _whisper_model
    
    if _llm_model is not None:
        unload_llm()
        
    if _whisper_model is None:
        print(f"Loading Whisper Model (Medium) from {MODELS_DIR}...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        

        local_pt = os.path.join(MODELS_DIR, "whisper", "medium.pt")
        if os.path.exists(local_pt):
            print(f"Found local model file: {local_pt}")
            print(f"Device: {device}. Loading local file directly...")
            _whisper_model = whisper.load_model(local_pt, device=device)
        else:
            root_pt = os.path.join(MODELS_DIR, "medium.pt")
            if os.path.exists(root_pt):
                 print(f"Found local model file at root: {root_pt}")
                 _whisper_model = whisper.load_model(root_pt, device=device)
            else:
                print(f"Device: {device}. Downloading/Loading model... (This may suck up bandwidth/time)")
                try:
                    _whisper_model = whisper.load_model("medium", device=device, download_root=MODELS_DIR)
                except Exception as e:
                    print(f"Error loading Whisper: {e}")
                    print("Trying default download...")
                    _whisper_model = whisper.load_model("medium", device=device)
    return _whisper_model

def get_embedder():
    global _embedder_model
    if _embedder_model is None:
        print("Loading Sentence Transformer...")
        _embedder_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device="cpu")
    return _embedder_model

def get_llm_model():
    global _llm_model
    
    if _whisper_model is not None:
        unload_whisper()
        
    if _llm_model is None:
        print("Loading LLM (Qwen 2.5 7B)...")
        if not os.path.exists(MODELS_DIR):
            os.makedirs(MODELS_DIR, exist_ok=True)
            
        target_file = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
        
        model_path = None
        print(f"Searching for {target_file} in {MODELS_DIR}...")
        
        for root, dirs, files in os.walk(MODELS_DIR):
            if target_file in files:
                model_path = os.path.join(root, target_file)
                print(f"Found model at: {model_path}")
                break
        
        if not model_path:
            print(f"Model {target_file} not found locally. Attempting fallback download...")
            repo = "bartowski/Qwen2.5-7B-Instruct-GGUF"
            try:
                model_path = hf_hub_download(repo_id=repo, filename=target_file)
            except Exception as e:
                 print(f"Download failed: {e}")
                 raise e
            
        _llm_model = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=-1,
            verbose=True
        )
    return _llm_model

async def transcribe_audio_safe(file_path: str, prompt: str = ""):
    async with GPU_LOCK:
        print(f"Acquired GPU Lock for Transcription: {file_path}")
    async with GPU_LOCK:
        print(f"Acquired GPU Lock for Transcription: {file_path}")
        
        if _whisper_model is None:
            print("Note: If this is the first run, Whisper model is downloading (1.5GB). This may take 5-10+ minutes. Please wait...", flush=True)

        loop = asyncio.get_event_loop()
        
        def _run():
            model = get_whisper_model()
            
            return model.transcribe(
                file_path, 
                initial_prompt=prompt,
                language="id",
                fp16=True,
                verbose=True
            )
            
        try:
            result = await loop.run_in_executor(None, _run)
            print("Released GPU Lock for Transcription")
            return result
        except RuntimeError as e:
            if "run out of memory" in str(e):
                raise Exception("GPU Out of Memory. Closing other apps may help.")
            raise e

async def generate_answer_safe(context: str, question: str):
    async with GPU_LOCK:
        print(f"Acquired GPU Lock for LLM Answer")
        llm = get_llm_model()
        
        loop = asyncio.get_event_loop()
        
        def _run():

            system_prompt = (
                "Anda adalah asisten ekstraksi data medis.\n"
                "Tugas anda adalah mengekstrak data spesifik dari transkrip.\n"
                "Jawab HANYA dengan data yang diminta. JANGAN gunakan kalimat lengkap.\n"
                "- Gunakan HANYA informasi dari 'Konteks Transkrip'. ABAIKAN pengetahuan luar.\n"
                "- Jika informasi tidak ada di konteks, katakan '-'. JANGAN mengarang.\n"
                "- Untuk nama, tulis HANYA namanya.\n"
                "- Untuk daftar, tulis item dipisahkan koma.\n"
            )
            
            user_prompt = f"Konteks Transkrip:\n{context}\n\nPertanyaan: {question}\nJawaban:"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            output = llm.create_chat_completion(
                messages=messages,
                max_tokens=300,
                temperature=0.3,
            )
            return output['choices'][0]['message']['content']
            
        result = await loop.run_in_executor(None, _run)
        print("Released GPU Lock for LLM")
        return result

if __name__ == "__main__":
    print("--- Healthvoice AI Check ---")
    print(f"Checking Model Path: {MODELS_DIR}")
    
    print("\n1. Testing Whisper Model...")
    try:
        w = get_whisper_model()
        print("Whisper Loaded successfully.")
    except Exception as e:
        print(f"Whisper Failed: {e}")

    print("\n2. Testing LLM (Qwen)...")
    try:
        l = get_llm_model()
        print("LLM Loaded successfully.")
    except Exception as e:
        print(f"LLM Failed: {e}")
        
    print("\nDone. If both checked out, run 'python app.py' to start server.")
