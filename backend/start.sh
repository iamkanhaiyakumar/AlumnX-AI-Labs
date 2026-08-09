#!/bin/bash
# Exit immediately if any command exits with a non-zero status
set -e

# Run Alembic migrations to create/update tables
alembic upgrade head

# Seed the database with the sales team roster
python -m app.seed

# Start the FastAPI application
uvicorn app.main:app --host 0.0.0.0 --port $PORT
