from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, ForeignKey, Enum as SqEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import uuid
import enum

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "../data/database.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"  
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class Transcript(Base):
    __tablename__ = "transcripts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, index=True)
    file_path = Column(String) 
    status = Column(SqEnum(ProcessingStatus), default=ProcessingStatus.QUEUED)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)
    process_start = Column(DateTime, nullable=True)
    process_end = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    raw_text = Column(Text, nullable=True)
    

    progress = Column(Integer, default=0)
    current_step = Column(String, default="Waiting in queue...") 
    

    qa_entries = relationship("QAEntry", back_populates="transcript")

class QAEntry(Base):
    __tablename__ = "qa_entries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transcript_id = Column(String, ForeignKey("transcripts.id"))
    
    question = Column(String)
    answer = Column(Text, nullable=True)
    context_used = Column(Text, nullable=True) 
    
    status = Column(SqEnum(ProcessingStatus), default=ProcessingStatus.QUEUED)
    
    transcript = relationship("Transcript", back_populates="qa_entries")

def init_db():
    Base.metadata.create_all(bind=engine)
    
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
