import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

load_dotenv()

DATABASE_URL = (
f"postgresql+psycopg2://"
f"{os.getenv('DB_USER')}:"
f"{os.getenv('DB_PASSWORD')}@"
f"{os.getenv('DB_HOST')}:"
f"{os.getenv('DB_PORT')}/"
f"{os.getenv('DB_NAME')}"
"?sslmode=require"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()