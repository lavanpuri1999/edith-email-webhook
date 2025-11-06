"""Gmail Push Notification Webhook Service"""

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import base64
import json
import asyncio
import uuid
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from celery_client import send_email_processing_task
from gmail_client import GmailClient
from database import lookup_person_and_token
from utils.logger import get_logger
from config.logging_config import setup_logging
from config.filters import message_matches_filters

# Initialize logging
setup_logging()

logger = get_logger("Webhook")

app = FastAPI(
    title="Gmail Webhook Service",
    description="Receives Gmail push notifications and queues emails for processing",
    version="1.0.0"
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request_id to each request for logging correlation"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    return response


# Request models
class GmailPushNotification(BaseModel):
    """Gmail push notification format"""
    message: dict
    subscription: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Gmail Webhook Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check for load balancers"""
    return {"status": "healthy"}


@app.post("/webhook/gmail/push")
async def gmail_push_webhook(request: Request):
    """
    Receive Gmail push notifications

    Gmail sends POST requests when new emails arrive:
    {
        "message": {
            "data": "base64-encoded-json",
            "messageId": "...",
            "publishTime": "..."
        }
    }

    The decoded data contains:
    {
        "emailAddress": "user@example.com",
        "historyId": "1234567"
    }
    """

    try:
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        body = await request.json()
        # Removed verbose "Received push notification" with full body - too verbose

        # Extract message data
        message = body.get('message', {})
        encoded_data = message.get('data')

        if not encoded_data:
            logger.warning("No data in push notification", extra={'request_id': request_id})
            return {"status": "ignored", "reason": "no_data"}

        # Decode base64 payload
        try:
            decoded_bytes = base64.b64decode(encoded_data)
            decoded_str = decoded_bytes.decode('utf-8')
            notification_data = json.loads(decoded_str)
        except Exception as e:
            logger.error(f"Failed to decode notification: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=400, detail="Invalid notification format")

        # Extract email address and history ID
        email_address = notification_data.get('emailAddress')
        history_id = notification_data.get('historyId')

        logger.info(f"Push notification received", extra={'request_id': request_id, 'email': email_address, 'history_id': history_id})

        if not email_address:
            logger.warning("No emailAddress in notification", extra={'request_id': request_id})
            return {"status": "ignored", "reason": "no_email_address"}

        # Lookup person_id, access token, and last historyId from database
        result = lookup_person_and_token(email_address, platform_id="gmail_platform_001")

        if not result:
            logger.warning(f"Unknown email address", extra={'request_id': request_id, 'email': email_address})
            return {
                "status": "ignored",
                "reason": "email_not_registered",
                "email": email_address
            }

        person_id, access_token, last_history_id = result
        # Removed verbose "Found person" message - log only if needed for debugging

        # Fetch new messages using Gmail History API
        gmail_client = GmailClient(access_token)

        # Determine which historyId to use as start point
        if last_history_id:
            # Use stored historyId to get all changes since last check
            start_history_id = last_history_id
            logger.info(f"Fetching history", extra={'request_id': request_id, 'person_id': person_id, 'start_history_id': start_history_id, 'end_history_id': history_id})
        else:
            # First time: No stored history, just save current historyId and skip processing
            logger.info(f"First notification, initializing historyId", extra={'request_id': request_id, 'person_id': person_id, 'email': email_address, 'history_id': history_id})
            from database import update_gmail_history_id
            update_gmail_history_id(person_id, "gmail_platform_001", str(history_id))
            return {
                "status": "ok",
                "processed": 0,
                "reason": "first_notification_historyId_initialized"
            }

        # Get history changes since last historyId
        history_data = await gmail_client.get_history(start_history_id)

        # Extract new message IDs from history
        message_ids = []
        history_records = history_data.get('history', [])

        for record in history_records:
            # messagesAdded contains new messages
            messages_added = record.get('messagesAdded', [])
            for msg_info in messages_added:
                message = msg_info.get('message', {})
                msg_id = message.get('id')
                if msg_id:
                    message_ids.append(msg_id)

        if not message_ids:
            logger.info(f"No new messages in history", extra={'request_id': request_id, 'person_id': person_id, 'start_history_id': start_history_id, 'end_history_id': history_id})
            # Update historyId even if no new messages (prevents reprocessing)
            from database import update_gmail_history_id
            update_gmail_history_id(person_id, "gmail_platform_001", str(history_id))
            return {
                "status": "ok",
                "processed": 0,
                "reason": "no_new_messages"
            }

        logger.info(f"Found {len(message_ids)} new messages", extra={'request_id': request_id, 'person_id': person_id, 'history_id': history_id})

        # Fetch and queue each message (with filtering)
        tasks_sent = 0
        filtered_count = 0

        for message_id in message_ids:
            # Fetch full message data
            message_data = await gmail_client.fetch_message_by_id(message_id)

            if not message_data:
                logger.warning(f"Failed to fetch message, skipping", extra={'request_id': request_id, 'person_id': person_id, 'message_id': message_id})
                continue

            # Check if message matches filters (safety net - Gmail should already filter at watch level)
            # This provides an extra layer of filtering in case Gmail's watch filter doesn't catch everything
            if not message_matches_filters(message_data):
                filtered_count += 1
                logger.debug(f"Message filtered out (doesn't match filters)", extra={'request_id': request_id, 'person_id': person_id, 'message_id': message_id})
                continue

            # Send to extraction service via Celery
            try:
                send_email_processing_task(
                    person_id=person_id,
                    platform_id="gmail_platform_001",
                    message_data=message_data
                )
                tasks_sent += 1
                # Removed verbose "Queued message" success message - too verbose

            except Exception as e:
                logger.error(f"Failed to queue message: {str(e)}", extra={'request_id': request_id, 'person_id': person_id, 'message_id': message_id}, exc_info=True)
                continue

        # Update stored historyId (even if some tasks failed, to prevent reprocessing)
        from database import update_gmail_history_id
        update_gmail_history_id(person_id, "gmail_platform_001", str(history_id))
        logger.info(f"Updated stored historyId", extra={'request_id': request_id, 'person_id': person_id, 'history_id': history_id, 'messages_found': len(message_ids), 'tasks_sent': tasks_sent, 'filtered': filtered_count})

        return {
            "status": "ok",
            "email": email_address,
            "person_id": person_id,
            "history_id": history_id,
            "messages_found": len(message_ids),
            "tasks_sent": tasks_sent,
            "filtered": filtered_count
        }

    except HTTPException:
        raise
    except Exception as e:
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        logger.error(f"Unexpected error: {str(e)}", extra={'request_id': request_id}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/webhook/gmail/manual")
async def manual_trigger(
    request: Request,
    email: str,
    message_id: Optional[str] = None
):
    """
    Manually trigger email processing (for testing)

    Args:
        email: User email address
        message_id: Optional specific message ID to fetch
    """
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))

    # Lookup person
    result = lookup_person_and_token(email, platform_id="gmail_platform_001")

    if not result:
        logger.warning(f"Email not registered", extra={'request_id': request_id, 'email': email})
        raise HTTPException(status_code=404, detail=f"Email not registered: {email}")

    person_id, access_token = result

    # Fetch message
    gmail_client = GmailClient(access_token)

    if message_id:
        # Fetch specific message
        message_data = await gmail_client.fetch_message_by_id(message_id)
        message_ids_to_process = [message_id] if message_data else []
    else:
        # Fetch latest message
        recent_ids = await gmail_client.list_recent_messages(max_results=1)
        message_ids_to_process = recent_ids

    if not message_ids_to_process:
        logger.warning(f"No messages found", extra={'request_id': request_id, 'person_id': person_id, 'email': email})
        raise HTTPException(status_code=404, detail="No messages found")

    # Process messages (with filtering)
    tasks_sent = 0
    filtered_count = 0
    for msg_id in message_ids_to_process:
        message_data = await gmail_client.fetch_message_by_id(msg_id)
        if message_data:
            # Check if message matches filters
            if not message_matches_filters(message_data):
                filtered_count += 1
                logger.debug(f"Message filtered out (doesn't match filters)", extra={'request_id': request_id, 'person_id': person_id, 'message_id': msg_id})
                continue
            
            send_email_processing_task(person_id, "gmail_platform_001", message_data)
            tasks_sent += 1

    logger.info(f"Manual trigger complete", extra={'request_id': request_id, 'person_id': person_id, 'email': email, 'tasks_sent': tasks_sent, 'filtered': filtered_count})
    return {
        "status": "ok",
        "email": email,
        "person_id": person_id,
        "tasks_sent": tasks_sent,
        "filtered": filtered_count
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
