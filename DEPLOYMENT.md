# Deployment Guide

Production deployment options for the Gmail Webhook Service.

---

## Deployment Architecture

```
Internet → Load Balancer → Webhook Service → RabbitMQ → Extraction Service
                                ↓                            ↓
                           PostgreSQL ← ← ← ← ← ← ← ← ← ← ←
```

**Key points:**
- Webhook service should be publicly accessible (for Gmail push notifications)
- RabbitMQ and PostgreSQL can be private
- Extraction service doesn't need public access

---

## Option 1: Docker Deployment

### 1. Build Docker image

```bash
docker build -t gmail-webhook:latest .
```

### 2. Run container

```bash
docker run -d \
  --name gmail-webhook \
  -p 8001:8001 \
  --env-file .env \
  --restart unless-stopped \
  gmail-webhook:latest
```

### 3. With docker-compose

```bash
docker-compose up -d
```

Monitor logs:
```bash
docker-compose logs -f webhook
```

---

## Option 2: Systemd Service (Linux)

### 1. Create service file

Create `/etc/systemd/system/gmail-webhook.service`:

```ini
[Unit]
Description=Gmail Webhook Service
After=network.target rabbitmq.service postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/gmail-webhook
Environment="PATH=/opt/gmail-webhook/venv/bin"
EnvironmentFile=/opt/gmail-webhook/.env
ExecStart=/opt/gmail-webhook/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Install and start

```bash
# Copy files
sudo cp -r . /opt/gmail-webhook
cd /opt/gmail-webhook

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable gmail-webhook
sudo systemctl start gmail-webhook

# Check status
sudo systemctl status gmail-webhook
```

### 3. View logs

```bash
sudo journalctl -u gmail-webhook -f
```

---

## Option 3: Cloud Deployment

### AWS (EC2 + ALB)

**Architecture:**
```
Route 53 → ALB → EC2 (Webhook) → RDS (PostgreSQL)
                  ↓                 Amazon MQ (RabbitMQ)
```

**Setup:**
1. Launch EC2 instance (t3.small or larger)
2. Install Docker or use systemd
3. Configure ALB health check: `/health`
4. Set up RDS PostgreSQL (or use existing)
5. Set up Amazon MQ (RabbitMQ)
6. Configure security groups

### Google Cloud (Cloud Run)

**Dockerfile** (already included)

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/gmail-webhook

# Deploy
gcloud run deploy gmail-webhook \
  --image gcr.io/PROJECT_ID/gmail-webhook \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL="..." \
  --set-env-vars CELERY_BROKER_URL="..." \
  --set-env-vars TOKEN_ENCRYPTION_KEY="..."
```

**Note:** Cloud Run may have cold starts. Consider Cloud Run with min instances or use GKE.

### Heroku

```bash
# Login
heroku login

# Create app
heroku create gmail-webhook-prod

# Set environment variables
heroku config:set DATABASE_URL="..."
heroku config:set CELERY_BROKER_URL="..."
heroku config:set TOKEN_ENCRYPTION_KEY="..."

# Deploy
git push heroku main
```

**Procfile:**
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### DigitalOcean App Platform

```yaml
# .do/app.yaml
name: gmail-webhook
services:
  - name: webhook
    github:
      repo: your-org/edith-gmail-webhook
      branch: main
    build_command: pip install -r requirements.txt
    run_command: uvicorn main:app --host 0.0.0.0 --port 8080
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${DATABASE_URL}
      - key: CELERY_BROKER_URL
        scope: RUN_TIME
        value: ${CELERY_BROKER_URL}
      - key: TOKEN_ENCRYPTION_KEY
        scope: RUN_TIME
        type: SECRET
    health_check:
      http_path: /health
```

---

## Nginx Reverse Proxy

If deploying behind Nginx:

```nginx
server {
    listen 80;
    server_name webhook.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

With SSL (Let's Encrypt):

```bash
sudo certbot --nginx -d webhook.yourdomain.com
```

---

## Environment Variables (Production)

**Critical:** Keep these secure!

```bash
# Database (use connection pooling in production)
DATABASE_URL=postgresql://user:password@db-host:5432/edith_prod

# RabbitMQ (use strong credentials)
CELERY_BROKER_URL=amqp://edith:STRONG_PASSWORD@rabbitmq-host:5672/edith_vhost

# Encryption key (NEVER reuse dev key in production!)
TOKEN_ENCRYPTION_KEY=PRODUCTION_KEY_HERE

# Optional: Sentry for error tracking
SENTRY_DSN=https://...@sentry.io/...
```

**Security tips:**
- Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
- Never commit `.env` file
- Rotate encryption key periodically
- Use strong database passwords

---

## Scaling

### Horizontal Scaling

Run multiple webhook service instances:

```bash
# Instance 1
docker run -d -p 8001:8001 --name webhook-1 gmail-webhook

# Instance 2
docker run -d -p 8002:8001 --name webhook-2 gmail-webhook

# Instance 3
docker run -d -p 8003:8001 --name webhook-3 gmail-webhook
```

Load balance with Nginx:

```nginx
upstream webhook_backend {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    location / {
        proxy_pass http://webhook_backend;
    }
}
```

### Resource Requirements

**Minimal:**
- CPU: 0.5 vCPU
- RAM: 512 MB
- Disk: 5 GB

**Recommended:**
- CPU: 1 vCPU
- RAM: 1 GB
- Disk: 10 GB

**High traffic (1000+ users):**
- CPU: 2 vCPU
- RAM: 2 GB
- Disk: 20 GB
- Multiple instances behind load balancer

---

## Monitoring

### Health Checks

```bash
# Basic health
curl http://localhost:8001/health

# Detailed status (add custom endpoint)
curl http://localhost:8001/status
```

### Logging

**Structured logging (add to main.py):**

```python
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or use structured JSON logging
import structlog
```

**Log aggregation:**
- AWS CloudWatch
- Google Cloud Logging
- Datadog
- Elasticsearch + Kibana

### Metrics

**Add Prometheus metrics:**

```bash
pip install prometheus-fastapi-instrumentator
```

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

**Monitor:**
- Request rate
- Response time
- Error rate
- Queue length (RabbitMQ)

### Alerting

Set up alerts for:
- Service down (health check fails)
- High error rate (> 5%)
- RabbitMQ connection failures
- Database connection failures

---

## Security Checklist

- [ ] HTTPS enabled (SSL/TLS certificate)
- [ ] Strong database passwords
- [ ] Firewall rules (restrict database/RabbitMQ access)
- [ ] Secrets stored in environment variables (not in code)
- [ ] Encryption key is production-specific
- [ ] Regular dependency updates (`pip list --outdated`)
- [ ] Rate limiting enabled
- [ ] CORS configured correctly
- [ ] Request validation enabled
- [ ] Error messages don't leak sensitive info

---

## Backup Strategy

### Database Backups

```bash
# Daily backup
pg_dump -h db-host -U user edith_prod > backup-$(date +%Y%m%d).sql

# Restore
psql -h db-host -U user edith_prod < backup-20240115.sql
```

### Environment Backups

Keep encrypted backups of:
- `.env` file
- Encryption keys
- Database credentials

---

## Rollback Plan

1. Keep previous Docker image:
   ```bash
   docker tag gmail-webhook:latest gmail-webhook:v1.0.0
   ```

2. Rollback if needed:
   ```bash
   docker stop gmail-webhook
   docker run -d --name gmail-webhook gmail-webhook:v1.0.0
   ```

3. Database migrations: Keep migration scripts

---

## Performance Tuning

### Database Connection Pool

```python
# database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

### Async Workers

```python
# uvicorn with multiple workers
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8001
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/webhook/gmail/push")
@limiter.limit("100/minute")
async def gmail_push_webhook(request: Request):
    ...
```

---

## Troubleshooting

### High Memory Usage

**Cause:** Too many concurrent requests

**Fix:**
- Limit uvicorn workers
- Add memory limits in Docker
- Scale horizontally

### Slow Response Times

**Cause:** Database queries or Gmail API calls

**Fix:**
- Add database indexes
- Use connection pooling
- Cache frequently accessed data

### RabbitMQ Connection Drops

**Cause:** Network issues or RabbitMQ restart

**Fix:**
- Add connection retry logic
- Use RabbitMQ cluster
- Monitor RabbitMQ health

---

## Maintenance

### Regular Tasks

**Daily:**
- Check service health
- Monitor error logs
- Check RabbitMQ queue depth

**Weekly:**
- Review error trends
- Check disk space
- Update dependencies (if needed)

**Monthly:**
- Security patches
- Performance review
- Backup verification

---

## Support Contacts

- **Service owner:** Your team
- **Database:** DBA team / managed service
- **RabbitMQ:** Infrastructure team
- **Gmail API:** Google Cloud support

---

## Useful Commands

```bash
# Check service status
systemctl status gmail-webhook

# Restart service
systemctl restart gmail-webhook

# View logs
journalctl -u gmail-webhook -f

# Check Docker container
docker ps | grep webhook
docker logs -f gmail-webhook

# Test endpoint
curl -X POST http://localhost:8001/webhook/gmail/manual?email=test@example.com

# Check RabbitMQ
curl -u guest:guest http://localhost:15672/api/queues

# Database query
psql $DATABASE_URL -c "SELECT COUNT(*) FROM emails WHERE created_at > NOW() - INTERVAL '1 hour';"
```

---

## Post-Deployment Checklist

- [ ] Service is running
- [ ] Health check passes
- [ ] Manual trigger works
- [ ] Logs are being collected
- [ ] Monitoring is active
- [ ] Alerts are configured
- [ ] SSL certificate is valid
- [ ] DNS is pointing correctly
- [ ] Firewall rules are set
- [ ] Backups are scheduled
- [ ] Documentation is updated
- [ ] Team is trained

---

You're ready for production! 🚀
