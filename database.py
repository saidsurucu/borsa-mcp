import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Fly.io otomatik olarak DATABASE_URL secret'ını sağlar
DATABASE_URL = os.environ.get("DATABASE_URL")

# SQLite fallback for local development
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./borsa_mcp.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()