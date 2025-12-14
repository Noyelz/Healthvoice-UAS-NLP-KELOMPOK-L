from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from contextlib import asynccontextmanager

from database import init_db
from routes import router
from services import background_worker
from models_ai import clear_vram

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initialize DB...")
    init_db()
    clear_vram()
    worker_task = asyncio.create_task(background_worker())
    
    yield
    
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        print("Worker stopped")
        
    clear_vram()

app = FastAPI(title="Healthvoice API", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "../data")
FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")

app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("  HEALTHVOICE SERVER IS READY")
    print("  👉 Click here to open: http://localhost:8000")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
