import os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from dotenv import dotenv_values

# Resolve the absolute path to the .env file in the workspace root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_file_path = os.path.join(BASE_DIR, ".env")

# Read raw dotenv values directly to extract multiple keys with different suffixes
env_vals = dotenv_values(env_file_path)

class Settings(BaseSettings):
    CANDIDATE_ID: str = Field(..., validation_alias="CANDIDATE_ID")
    DATABASE_URL: str = Field(..., validation_alias="DATABASE_URL")
    FRONTEND_URL: str = Field("http://localhost:5173", validation_alias="FRONTEND_URL")
    GEMINI_MODEL: str = Field("gemini-2.0-flash", validation_alias="GEMINI_MODEL")
    
    # Placeholders to be populated dynamically
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEYS: list[str] = []

    @field_validator("CANDIDATE_ID", mode="before")
    @classmethod
    def validate_and_normalize_candidate_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("CANDIDATE_ID must be a string")
        v = v.strip().lower()
        v = v.replace(",", ".")
        if v != "kanhaiyak0104@gmail.com":
            raise ValueError(f"CANDIDATE_ID must be exactly kanhaiyak0104@gmail.com, got {v}")
        return v

    class Config:
        env_file = env_file_path
        extra = "ignore"

settings = Settings()

# Dynamically gather all Gemini API Keys from .env and system env
keys_list = []

# 1. Read keys from the .env file
for k, v in env_vals.items():
    if k.startswith("GEMINI_API_KEY") and v:
        keys_list.append(v.strip())

# 2. If no keys were found in the .env file, fallback to system environment variables
if not keys_list:
    for k, v in os.environ.items():
        if k.startswith("GEMINI_API_KEY") and v:
            keys_list.append(v.strip())

# Deduplicate keys while maintaining order
seen = set()
unique_keys = []
for key in keys_list:
    if key not in seen:
        seen.add(key)
        unique_keys.append(key)

# Populate settings properties
settings.GEMINI_API_KEYS = unique_keys
settings.GEMINI_API_KEY = unique_keys[0] if unique_keys else ""
