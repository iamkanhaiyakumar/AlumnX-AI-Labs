from urllib.parse import unquote
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# Parse the database URL and unquote the database name to handle spaces properly
db_url = make_url(settings.DATABASE_URL)

# Force use of modern psycopg v3 driver to prevent psycopg2 ModuleNotFoundError on standard URLs
if db_url.drivername in ("postgresql", "postgres"):
    db_url = db_url.set(drivername="postgresql+psycopg")

if db_url.database and ("%" in db_url.database or "%20" in db_url.database):
    db_url = db_url.set(database=unquote(db_url.database))

# Setup SQLAlchemy connection engine for PostgreSQL
engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
