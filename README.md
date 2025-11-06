# Gmail Webhook Service

This service receives Gmail push notifications and queues emails for processing by the extraction service.

## 🚀 TL;DR - Quick Start with Docker

```bash
# 1. Create .env file
cat > .env << 'EOF'
DATABASE_URL=postgresql://user:password@host.docker.internal:5432/edith_db
CELERY_BROKER_URL=amqp://guest:guest@host.docker.internal:5672//
TOKEN_ENCRYPTION_KEY=your-encryption-key-from-extraction-service
EOF

# 2. Build and run
docker build -t gmail-webhook .
docker run -d --name gmail-webhook -p 8001:8001 --env-file .env gmail-webhook

# 3. Verify
curl http://localhost:8001/health
# Should return: {"status":"healthy"}
```

**Or with docker-compose:**
```bash
docker-compose up -d
```

📖 [See detailed instructions below](#quick-start-docker---recommended)

---

## Architecture

```
Gmail Push Notification → Webhook Service → Celery Task → Extraction Service
                              ↓
                        Fetch from Gmail
                              ↓
                        Send to RabbitMQ
```

**This service:**
- Receives Gmail push notifications
- Fetches email data from Gmail API
- Sends task to RabbitMQ for extraction service to process

**Does NOT:**
- Run Celery workers (just sends tasks)
- Process emails or do LLM extraction
- Store emails in database (extraction service does that)

---

## Quick Start (Docker - Recommended)

### Prerequisites

Before starting:
- ✅ Docker and Docker Compose installed
- ✅ Extraction service running (or at least its database and RabbitMQ)
- ✅ PostgreSQL database with extraction service schema
- ✅ RabbitMQ instance (can be shared with extraction service)

---

### Step 1: Clone and Navigate

```bash
cd /path/to/edith-gmail-webhook
```

---

### Step 2: Create Environment File

Create a `.env` file with your configuration:

```bash
# Create .env file
cat > .env << 'EOF'
# Database (same as extraction service)
DATABASE_URL=postgresql://user:password@localhost:5432/edith_db

# RabbitMQ (same as extraction service)
# Use 'rabbitmq' if running via docker-compose, or 'localhost' if external
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//

# Token Encryption Key (same as extraction service)
TOKEN_ENCRYPTION_KEY=your-32-character-encryption-key-here
EOF
```

**Important:** Use the **exact same values** as your extraction service!

**To get your encryption key from extraction service:**
```bash
cd ../edith-email-extractor
grep TOKEN_ENCRYPTION_KEY .env
# Copy the value to webhook .env
```

---

### Step 3: Choose Your Setup

#### **Option A: Standalone (Connect to Existing Services)** ⭐ Recommended

If you already have RabbitMQ and PostgreSQL running (e.g., from extraction service):

**Update `.env` to point to existing services:**
```bash
# Use host.docker.internal to connect to services on host machine
DATABASE_URL=postgresql://user:password@host.docker.internal:5432/edith_db
CELERY_BROKER_URL=amqp://guest:guest@host.docker.internal:5672//
TOKEN_ENCRYPTION_KEY=your-encryption-key-from-extraction-service
```

**Start only the webhook service:**
```bash
# Build the image
docker build -t gmail-webhook .

# Run the container
docker run -d \
  --name gmail-webhook \
  -p 8001:8001 \
  --env-file .env \
  gmail-webhook

# Check logs
docker logs -f gmail-webhook
```

**On Linux, use Docker network instead:**
```bash
# Find extraction service network
docker network ls

# Run webhook on same network
docker run -d \
  --name gmail-webhook \
  -p 8001:8001 \
  --network edith-email-extractor_default \
  --env-file .env \
  gmail-webhook
```

---

#### **Option B: Full Stack (Webhook + RabbitMQ)**

If you want to run RabbitMQ along with the webhook:

**Update `.env` for docker-compose:**
```bash
DATABASE_URL=postgresql://user:password@host.docker.internal:5432/edith_db
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
TOKEN_ENCRYPTION_KEY=your-encryption-key
```

**Start all services:**
```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# Check logs
docker-compose logs -f webhook
```

This will start:
- ✅ Webhook service on port 8001
- ✅ RabbitMQ on ports 5672 (AMQP) and 15672 (Management UI)

---

### Step 4: Verify It's Running

```bash
# Check health
curl http://localhost:8001/health

# Expected response:
{"status":"healthy"}

# Check service info
curl http://localhost:8001/

# Expected response:
{
  "service": "Gmail Webhook Service",
  "status": "running",
  "version": "1.0.0"
}
```

**Check container is running:**
```bash
# Using docker run
docker ps | grep gmail-webhook

# Using docker-compose
docker-compose ps
```

---

### Step 5: Test Manual Trigger

```bash
# Replace with an email that exists in your database
curl -X POST "http://localhost:8001/webhook/gmail/manual?email=YOUR_EMAIL@gmail.com"

# Expected response:
{
  "status": "ok",
  "email": "user@example.com",
  "person_id": "abc-123-uuid",
  "tasks_sent": 1
}
```

---

### Useful Docker Commands

```bash
# View logs
docker logs -f gmail-webhook
# or
docker-compose logs -f webhook

# Stop service
docker stop gmail-webhook
# or
docker-compose stop

# Restart service
docker restart gmail-webhook
# or
docker-compose restart webhook

# Stop and remove
docker rm -f gmail-webhook
# or
docker-compose down

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d

# Check resource usage
docker stats gmail-webhook
```

---

### Troubleshooting Docker Setup

#### Issue: Container exits immediately

**Check logs:**
```bash
docker logs gmail-webhook
```

**Common causes:**
- ❌ Missing or invalid `.env` file
- ❌ Can't connect to database
- ❌ Can't connect to RabbitMQ

**Fix:**
```bash
# Test database connection
docker run --rm --env-file .env gmail-webhook \
  python -c "from database import get_db; get_db()"

# Test RabbitMQ connection
docker run --rm --env-file .env gmail-webhook \
  python test_connection.py
```

#### Issue: Can't connect to host services

**Error:** `Connection refused` when connecting to localhost

**Fix:** Use `host.docker.internal` instead of `localhost`:
```bash
# In .env
DATABASE_URL=postgresql://user:password@host.docker.internal:5432/edith_db
CELERY_BROKER_URL=amqp://guest:guest@host.docker.internal:5672//
```

**On Linux:** Add `--add-host=host.docker.internal:host-gateway`
```bash
docker run -d \
  --add-host=host.docker.internal:host-gateway \
  --name gmail-webhook \
  -p 8001:8001 \
  --env-file .env \
  gmail-webhook
```

#### Issue: Port 8001 already in use

**Fix:** Use a different port:
```bash
# Map to different host port (e.g., 8002)
docker run -d -p 8002:8001 --name gmail-webhook --env-file .env gmail-webhook

# Access at http://localhost:8002
```

#### Issue: Database/RabbitMQ not found

**Fix:** Make sure services are running:
```bash
# Check PostgreSQL
psql -h localhost -U user -d edith_db

# Check RabbitMQ
curl http://localhost:15672
# Login: guest/guest
```

---

## Deployment Scenarios

### Scenario 1: Same Server as Extraction Service

```bash
# Both services share database and RabbitMQ
# Webhook runs in Docker, extraction service on host

# In .env:
DATABASE_URL=postgresql://user:password@host.docker.internal:5432/edith_db
CELERY_BROKER_URL=amqp://guest:guest@host.docker.internal:5672//

# Run webhook
docker run -d -p 8001:8001 --name gmail-webhook --env-file .env gmail-webhook
```

### Scenario 2: Separate Server

```bash
# Webhook on different server, connects to remote services

# In .env:
DATABASE_URL=postgresql://user:password@db.example.com:5432/edith_db
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq.example.com:5672//

# Run webhook
docker run -d -p 8001:8001 --name gmail-webhook --env-file .env gmail-webhook
```

### Scenario 3: All Services in Docker

```bash
# Everything runs in Docker with docker-compose

# Use docker-compose.yml as-is
docker-compose up -d

# Services communicate via Docker network
```

---

## Alternative: Manual Setup (Without Docker)

<details>
<summary>Click to expand manual installation steps</summary>

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Start the Service

```bash
python main.py
```

Or with uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Service will be available at: `http://localhost:8001`

</details>

---

## Endpoints

### 1. **POST /webhook/gmail/push**

Receives Gmail push notifications (configured in Google Cloud Console)

**Request format (sent by Gmail):**
```json
{
  "message": {
    "data": "base64-encoded-notification",
    "messageId": "...",
    "publishTime": "..."
  }
}
```

**Response:**
```json
{
  "status": "ok",
  "email": "user@example.com",
  "person_id": "uuid",
  "history_id": "1234567",
  "messages_found": 3,
  "tasks_sent": 3
}
```

### 2. **POST /webhook/gmail/manual**

Manually trigger email processing (for testing)

**Query params:**
- `email` (required): User email address
- `message_id` (optional): Specific message ID to process

**Example:**
```bash
curl -X POST "http://localhost:8001/webhook/gmail/manual?email=user@example.com"
```

### 3. **GET /**

Service info and health check

### 4. **GET /health**

Simple health check for load balancers

---

## How It Works

### 1. Gmail sends push notification

When a new email arrives, Gmail sends a webhook to `/webhook/gmail/push`

### 2. Decode notification

The service decodes the base64 payload to get:
- `emailAddress`: User's email
- `historyId`: Gmail history marker

### 3. Lookup person

Query database to find `person_id` and `access_token` for the email address

### 4. Fetch new messages

Use Gmail History API to fetch messages since `historyId`

### 5. Queue each message

For each new message:
- Fetch full message data from Gmail API
- Send Celery task to extraction service:
  ```python
  celery_app.send_task(
      'tasks.single_email_task.process_single_email_task',
      args=[person_id, platform_id],
      kwargs={'message_data': message_data},
      queue='high_priority'
  )
  ```

### 6. Return response

Return count of messages queued

---

## Gmail Push Notification Setup

### 1. Create Google Cloud Pub/Sub Topic

```bash
gcloud pubsub topics create gmail-push-notifications
```

### 2. Grant Gmail permissions

```bash
gcloud pubsub topics add-iam-policy-binding gmail-push-notifications \
  --member='serviceAccount:gmail-api-push@system.gserviceaccount.com' \
  --role='roles/pubsub.publisher'
```

### 3. Create Pub/Sub subscription

```bash
gcloud pubsub subscriptions create gmail-webhook-subscription \
  --topic=gmail-push-notifications \
  --push-endpoint=https://your-domain.com/webhook/gmail/push
```

### 4. Watch Gmail mailbox (per user)

```bash
POST https://gmail.googleapis.com/gmail/v1/users/me/watch
Authorization: Bearer USER_ACCESS_TOKEN

{
  "topicName": "projects/YOUR_PROJECT/topics/gmail-push-notifications",
  "labelIds": ["INBOX"]
}
```

**Response:**
```json
{
  "historyId": "1234567",
  "expiration": "1640000000000"
}
```

**Note:** Watch expires after 7 days, need to renew periodically.

---

## Testing

### 1. Start RabbitMQ

```bash
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

### 2. Start Extraction Service Workers

In the extraction service directory:
```bash
celery -A celery_app worker --queues high_priority,priority_low --concurrency 20 --loglevel info
```

### 3. Start Webhook Service

```bash
python main.py
```

### 4. Manually trigger processing

```bash
curl -X POST "http://localhost:8001/webhook/gmail/manual?email=user@example.com"
```

### 5. Monitor tasks

Visit RabbitMQ management: `http://localhost:15672` (guest/guest)

Or use Celery Flower in extraction service:
```bash
celery -A celery_app flower
```

---

## Project Structure

```
edith-gmail-webhook/
├── main.py                 # FastAPI app with webhook endpoints
├── celery_client.py        # Celery client for sending tasks
├── gmail_client.py         # Gmail API client
├── database.py             # Database lookup helpers
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

---

## Environment Requirements

- **Python**: 3.9+
- **RabbitMQ**: 3.x (same instance as extraction service)
- **PostgreSQL**: 14+ (same database as extraction service)
- **Network**: Must be able to connect to:
  - Gmail API (googleapis.com)
  - RabbitMQ broker
  - PostgreSQL database

---

## Deployment

### Option 1: Same server as extraction service

```bash
# Run on different port
uvicorn main:app --host 0.0.0.0 --port 8001
```

### Option 2: Separate server

Ensure the webhook service can:
- Connect to same RabbitMQ instance
- Connect to same PostgreSQL database

### Option 3: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
docker build -t gmail-webhook .
docker run -p 8001:8001 --env-file .env gmail-webhook
```

---

## Monitoring

### Check webhook service health

```bash
curl http://localhost:8001/health
```

### View logs

Service logs show:
- Incoming push notifications
- Person lookups
- Messages fetched
- Tasks sent

Example:
```
[Webhook] Received push notification
[Webhook] Push notification for user@example.com, historyId: 1234567
[Database] Found person abc-123 for user@example.com
[Webhook] Found 2 new messages: ['abc123', 'def456']
[Webhook] ✓ Queued message abc123 for processing
[Webhook] ✓ Queued message def456 for processing
```

### Monitor RabbitMQ queue

Visit: http://localhost:15672

Check `high_priority` queue for queued tasks

---

## Error Handling

### User not found
- **Cause**: Email address not registered in system
- **Response**: `{"status": "ignored", "reason": "email_not_registered"}`
- **Action**: User needs to complete onboarding first

### Token expired
- **Cause**: OAuth token expired/invalid
- **Response**: Gmail API returns 401
- **Action**: Extraction service handles token refresh

### No new messages
- **Cause**: History API returns no changes
- **Response**: `{"status": "ok", "processed": 0}`
- **Action**: Normal, nothing to process

### Task sending fails
- **Cause**: RabbitMQ connection issue
- **Response**: Exception logged
- **Action**: Check RabbitMQ is running and accessible

---

## Security

### Authentication

Gmail push notifications are authenticated via:
1. Google Cloud Pub/Sub push endpoint verification
2. Signed JWT in request headers (can be validated)

### Token encryption

OAuth tokens are encrypted in database using Fernet symmetric encryption.

### Network security

Recommendations:
- Use HTTPS in production (`https://your-domain.com`)
- Restrict webhook endpoint to Google IP ranges
- Use environment variables for sensitive data

---

## Docker Quick Reference

### Start Service

```bash
# Using docker run (standalone)
docker run -d --name gmail-webhook -p 8001:8001 --env-file .env gmail-webhook

# Using docker-compose (with RabbitMQ)
docker-compose up -d
```

### View Logs

```bash
docker logs -f gmail-webhook           # Follow logs
docker logs --tail 100 gmail-webhook   # Last 100 lines
docker-compose logs -f webhook         # docker-compose version
```

### Stop/Start/Restart

```bash
docker stop gmail-webhook              # Stop
docker start gmail-webhook             # Start
docker restart gmail-webhook           # Restart
docker-compose stop                    # Stop all
docker-compose restart webhook         # Restart webhook
```

### Update After Code Changes

```bash
# Rebuild and restart
docker stop gmail-webhook
docker rm gmail-webhook
docker build -t gmail-webhook .
docker run -d --name gmail-webhook -p 8001:8001 --env-file .env gmail-webhook

# Or with docker-compose
docker-compose build --no-cache
docker-compose up -d
```

### Debug

```bash
# Get shell inside container
docker exec -it gmail-webhook /bin/bash

# Test database connection
docker exec gmail-webhook python -c "from database import get_db; print('✓ DB connected')"

# Test RabbitMQ connection
docker exec gmail-webhook python test_connection.py

# Check resource usage
docker stats gmail-webhook
```

### Cleanup

```bash
# Remove container
docker rm -f gmail-webhook

# Remove image
docker rmi gmail-webhook

# Full cleanup with docker-compose
docker-compose down -v  # Remove containers and volumes
```

---

## FAQ

**Q: Does this service need Celery workers?**
A: No, it only sends tasks. Workers run in extraction service.

**Q: Can I deploy this on a different server?**
A: Yes, as long as it can connect to RabbitMQ and PostgreSQL.

**Q: What happens if extraction service is down?**
A: Tasks queue up in RabbitMQ, processed when service comes back.

**Q: How do I renew Gmail watch?**
A: Call Gmail watch API every 7 days (or set up automated renewal).

**Q: Can I test without Gmail push notifications?**
A: Yes, use `/webhook/gmail/manual` endpoint for testing.

---

## Related Services

- **Extraction Service**: Processes emails, stores in DB, runs LLM extraction
  - Repo: `edith-email-extractor/`
  - Runs Celery workers
  - Listens to `high_priority` queue

---

## Support

For issues or questions, check:
1. RabbitMQ is running and accessible
2. Database connection is working
3. Extraction service workers are running
4. Environment variables are set correctly
