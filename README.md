# Sales Inbox → Task Router System

Built for the **AlumnX AI Labs FDE Intern Hiring Challenge**.

---

## 1. Candidate Identity
- **CANDIDATE_ID**: `kanhaiyak0104@gmail.com`
- This candidate ID is normalized, trimmed, and byte-identical across the local `.env`, database configuration, headers, APIs, and documentation.

---

## 2. System Architecture

The project is structured as a decoupled full-stack application:

```text
├── backend/
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── routers/            # API Router definitions (tasks, users, ingest, api_stats, api_chat)
│   │   ├── services/           # Business services (gemini, spam, normalizer, priority, classifier, chat)
│   │   ├── config.py           # Application configurations and env validations
│   │   ├── database.py         # SQLAlchemy engine and connection pool pool config
│   │   ├── models.py           # PostgreSQL ORM schemas
│   │   ├── schemas.py          # Pydantic validation schemas
│   │   ├── seed.py             # Database user roster seed script
│   │   └── main.py             # FastAPI App entrypoint
│   ├── requirements.txt        # Backend python dependencies
│   └── tests/                  # Automated pytest test suite
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   │   └── sampleGenerator.js  # Generator for 250 realistic emails
│   │   ├── App.jsx             # React dashboard component
│   │   ├── index.css           # Premium vanilla CSS styling system
│   │   └── config.js           # API connection configurations
│   ├── package.json            # Node project configuration
│   └── index.html              # HTML entry point
├── README.md                   # Setup guide
├── DECISIONS.md                # System design rationale
└── EVALS.md                    # Evaluation reports
```

---

## 3. Quickstart Guide (Windows Setup)

### Prerequisites
- Python 3.10+
- Node.js v18+
- PostgreSQL server active on port 5432.

### Step 1: Clone and Configure Environment
Copy `.env.example` to `.env` in the root directory and ensure the database credentials match:
```env
CANDIDATE_ID=kanhaiyak0104@gmail.com
DATABASE_URL=postgresql+psycopg://postgres:Kanhaiya123@localhost:5432/AlumnX AI Labs
GEMINI_API_KEY=AIzaSyBMvYijPDtnIIpODNAhihwJbXXaTaVaqIU
FRONTEND_URL=http://localhost:5173
```

### Step 2: Initialize and Start the Backend
1. Open PowerShell or Command Prompt, navigate to the `backend` directory, and create a virtual environment:
   ```cmd
   cd backend
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install python dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
3. Run Alembic database migrations:
   ```cmd
   alembic upgrade head
   ```
4. Seed the database with the team roster:
   ```cmd
   python app/seed.py
   ```
5. Launch the FastAPI Uvicorn server:
   ```cmd
   python app/main.py
   ```
The backend API is now running at [http://localhost:8000](http://localhost:8000) with interactive documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

### Step 3: Initialize and Start the Frontend
1. Open another terminal in the `frontend` directory:
   ```cmd
   cd frontend
   ```
2. Install node dependencies:
   ```cmd
   npm install
   ```
3. Start the Vite React development server:
   ```cmd
   npm run dev
   ```
The frontend dashboard will be available at [http://localhost:5173](http://localhost:5173).

---

## 4. Ingestion API Spec

### Ingest Batch
- **Endpoint**: `POST /ingest`
- **Body Schema**:
  ```json
  {
    "candidate_id": "kanhaiyak0104@gmail.com",
    "emails": [
      {
        "email_id": "em_001",
        "thread_id": "th_001",
        "message_index": 0,
        "from_name": "Suresh Kulkarni",
        "from_email": "s.kulkarni@meridiansteel.co.in",
        "to": "sales@company.com",
        "cc": [],
        "subject": "RFP - Enterprise DMS",
        "body": "We invite proposals. Budget is Rs. 25 lakhs...",
        "received_at": "2026-08-01T09:14:22Z",
        "attachments": [],
        "is_reply": false
      }
    ]
  }
  ```
- **Response Schema**:
  ```json
  {
    "processed": 1,
    "tasks_created": 1,
    "tasks_updated": 0,
    "skipped": 0,
    "errors": []
  }
  ```

---

## 5. Running the Test Suite
To verify migrations, worked examples, idempotency, concurrent transactions, and grader simulation, run pytest inside the `backend` folder:
```cmd
cd backend
pytest
```
All tests should pass.
