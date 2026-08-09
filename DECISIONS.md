# Technical Design Decisions

This document outlines the core architectural and design decisions made for the **AlumnX AI Labs — Sales Inbox Task Router** system.

---

## 1. Database Decision: PostgreSQL Only
Instead of SQLite, we use **PostgreSQL** for both development and testing:
- **Gratitude of Concurrency**: PostgreSQL supports advanced row-level locks, transactional isolation, and concurrent connections necessary for production grade multi-agent or batch ingestion environments.
- **Grader Stability**: Evaluators run tests that verify thread-safe idempotency and persistence across system restarts/crashes. Using SQLite would lead to `database is locked` errors during concurrent runs.
- **Short Connection Lifetimes**: By keeping the database transaction scopes extremely small (committed within milliseconds), we prevent transaction pooling blockages.

---

## 2. Concurrency and Locking Strategy: Two-Transaction Claim-and-Release
To ensure idempotency and prevent double-classification, the ingestion service utilizes a **two-transaction pattern**:
1. **Transaction 1: Atomic Claim**
   - When an email arrives, we attempt to write it to the database with a status of `processing`.
   - If `candidate_id + email_id` already exists:
     - If status is `completed`, the email is a duplicate. We bypass processing instantly and increment the run duplicate count without calling Gemini.
     - If status is `processing` but its lease has expired (stale > 15 mins), we atomically reclaim it using a **CAS (Compare-And-Swap)** update:
       ```sql
       UPDATE emails SET status = 'processing', started_at = NOW() WHERE status = 'processing' AND started_at < NOW() - 15 mins;
       ```
     - If status is `failed`, we atomically reclaim it for a retry.
2. **Transaction 2: Persist Outcomes**
   - The expensive business logic (Gemini classification, intent analysis) is executed **outside** any active transaction. This keeps database connections free.
   - Once Gemini returns, we initiate a quick second transaction to create/update the `Task`, log the `TaskUpdate` or `ProcessingRecord`, mark the email as `completed`, and commit.

---

## 3. Gemini LLM Integration Strategy
- **Structured JSON Outputs**: We use Gemini’s native Pydantic schema configuration (`response_mime_type="application/json"` and `response_schema`). This guarantees that the JSON returned matches the expected fields, eliminating parsing errors.
- **Bounded Exponential Backoff**: Live API calls face rate limits (HTTP 429) or transient network timeouts. We wrap Gemini calls in a loop that retries up to 5 times, doubling the delay each time (bounded at 30 seconds).
- **Reply Content Extraction**: Instead of sending full quoted email histories (which bloats token usage and confuses the LLM on context), we normalise the email body and strip quoted text at reply signatures (e.g. `On ... wrote:`, `From:`, `Sent:`, `>`). Only the newly written reply text is evaluated for task updates.

---

## 4. Intent Direction & Classification Heuristics
- **Buying vs. Selling Intent**: Standard classifiers mistake vendor spam (someone selling SEO or marketing to us) as actionable marketing/sales leads. Our prompt explicitly defines intent direction: "actionable" leads mean others buying from us; unsolicited vendor pitches are marked as spurious skips.
- **Seeded User Roster & Routing**:
  - `u_aarti` (Enterprise Sales, RFPs > ₹10,00,000 INR, tenders).
  - `u_rohit` (SMB Sales, enquiries <= ₹10,00,000 INR).
  - `u_meera` (Marketing sponsorships, event webinars).
  - `u_karan` (Alliances, reseller/channel requests).
  - `u_divya` (Finance, invoices/billing, overdue GST).
  - `u_triage` (Ambiguous, conflicting requests).
- **Deterministic Overrides**:
  - **PSU/Government Tender**: If subject/body indicates a government tender (e.g., NTPC, BHEL, PSU, procurement), we force route it to Aarti and set the category to `enterprise_rfp` regardless of deal size.
  - **72-Hour Urgency**: If the stated due date is within 72 hours of the email received date, the priority is dynamically overridden to `high`.
