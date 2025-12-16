from sqlalchemy import create_engine, text
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "../data/database.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL)

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE qa_entries ADD COLUMN bleu_score FLOAT DEFAULT 0.0"))
            print("Successfully added 'bleu_score' column.")
        except Exception as e:
            if "duplicate column name" in str(e):
                print("Column 'bleu_score' already exists. Skipping.")
            else:
                print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
