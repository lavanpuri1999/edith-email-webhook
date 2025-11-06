"""Celery client for sending tasks to extraction service"""

from celery import Celery
import os
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()

logger = get_logger("CeleryClient")

# Initialize Celery client (no workers, just for sending tasks)
celery_app = Celery(
    'gmail_webhook_client',
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//'),
    backend='rpc://'
)

# Configure
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


def send_email_processing_task(person_id: str, platform_id: str, message_data: dict):
    """
    Send email processing task to extraction service

    Args:
        person_id: Person ID (owner of email account)
        platform_id: Platform identifier (e.g., "gmail_platform_001")
        message_data: Full Gmail API message response

    Returns:
        AsyncResult object (can be used to track task)
    """

    result = celery_app.send_task(
        'tasks.single_email_task.process_single_email_task',
        args=[person_id, platform_id],
        kwargs={'message_data': message_data},
        queue='priority_low',  # Background processing for incoming emails
        priority=1  # Low priority
    )

    # Removed verbose "Sent task" message - too verbose for each message
    # Log only on errors (handled in main.py)

    return result
