# Quick Start Guide

Get the Gmail Webhook Service running in 5 minutes.

## Prerequisites

- Python 3.9+
- RabbitMQ running (from extraction service)
- PostgreSQL database (from extraction service)
- Extraction service workers running

---

## Step 1: Install Dependencies

```bash
cd edith-gmail-webhook
pip install -r requirements.txt
```

---

## Step 2: Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your values:

```bash
# Use SAME values as extraction service
DATABASE_URL=postgresql://user:password@localhost:5432/edith_db
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
TOKEN_ENCRYPTION_KEY=your-encryption-key-from-extraction-service
```

**Important:** Use the **exact same** values as your extraction service!

---

## Step 3: Test Connections

```bash
python test_connection.py
```

Expected output:
```
✓ Environment Variables
✓ Database connected successfully (123 persons in database)
✓ RabbitMQ connected successfully
✓ All tests passed!
```

If tests fail, check your `.env` file.

---

## Step 4: Start the Service

```bash
python main.py
```

Or with auto-reload:
```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Service will be available at: **http://localhost:8001**

---

## Step 5: Test Manual Processing

Open another terminal and test:

```bash
curl -X POST "http://localhost:8001/webhook/gmail/manual?email=YOUR_EMAIL@gmail.com"
```

Replace `YOUR_EMAIL@gmail.com` with an email that's registered in your system.

Expected response:
```json
{
  "status": "ok",
  "email": "user@example.com",
  "person_id": "abc-123-uuid",
  "tasks_sent": 1
}
```

---

## Step 6: Monitor Task Processing

### Option 1: Check RabbitMQ

Visit: http://localhost:15672 (guest/guest)

Look at `high_priority` queue - you should see tasks being processed.

### Option 2: Check Extraction Service Logs

In your extraction service terminal, you should see:
```
[SingleEmail] Processing pre-fetched message abc12345
[EmailProcessor] Stored email abc12345 with ID xyz789
[SingleEmail] Email abc12345 stored with ID xyz789
[SingleEmail] LLM extraction task triggered
```

---

## Verify It's Working

### 1. Check webhook service health

```bash
curl http://localhost:8001/health
```

Response:
```json
{"status": "healthy"}
```

### 2. Check database

In your database, check the `emails` table:
```sql
SELECT id, subject, sender, date
FROM emails
ORDER BY created_at DESC
LIMIT 5;
```

You should see newly fetched emails.

### 3. Check task completion

Wait 30 seconds, then check `extracted_data` field:
```sql
SELECT id, subject, extracted_data
FROM emails
WHERE extracted_data IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

The `extracted_data` should contain LLM extraction results.

---

## Common Issues

### Issue: Database connection fails

**Error:** `could not connect to server`

**Fix:**
- Verify PostgreSQL is running
- Check `DATABASE_URL` in `.env`
- Use same URL as extraction service

### Issue: RabbitMQ connection fails

**Error:** `[Errno 61] Connection refused`

**Fix:**
- Verify RabbitMQ is running: `docker ps`
- Check `CELERY_BROKER_URL` in `.env`
- Start RabbitMQ: `docker run -d -p 5672:5672 rabbitmq`

### Issue: Person not found

**Error:** `{"status": "ignored", "reason": "email_not_registered"}`

**Fix:**
- User needs to complete onboarding first
- Check email exists in database: `SELECT * FROM persons WHERE primary_email = 'user@example.com'`

### Issue: Tasks not processing

**Symptoms:** Tasks sent but not processed

**Fix:**
- Check extraction service workers are running
- In extraction service directory: `celery -A celery_app worker --queues high_priority --loglevel info`

---

## Next Steps

### Setup Gmail Push Notifications

For real-time notifications from Gmail, follow the full setup in `README.md`:

1. Create Google Cloud Pub/Sub topic
2. Configure push subscription
3. Watch user mailboxes

### Deploy to Production

See `README.md` for deployment options:
- Docker container
- Separate server
- Same server as extraction service

---

## Architecture Recap

```
Gmail → Webhook Service → RabbitMQ → Extraction Workers → Database
         (fetch email)    (queue)      (process + LLM)     (store)
```

**This service (webhook):**
- Receives notifications
- Fetches emails
- Queues tasks

**Extraction service:**
- Processes tasks
- Stores emails
- Runs LLM extraction

---

## Useful Commands

```bash
# Start webhook service
python main.py

# Test connections
python test_connection.py

# Manual trigger
curl -X POST "http://localhost:8001/webhook/gmail/manual?email=user@example.com"

# Check health
curl http://localhost:8001/health

# View API docs
# Visit http://localhost:8001/docs
```

---

## Need Help?

1. Check logs in terminal
2. Verify RabbitMQ is running
3. Verify extraction service workers are running
4. Check `.env` variables match extraction service
5. Run `python test_connection.py`

---

You're all set! 🚀

The webhook service is now receiving emails and queuing them for processing.
