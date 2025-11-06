"""Gmail API client for fetching messages"""

import httpx
from typing import Optional, Dict, Any, List
from utils.logger import get_logger

logger = get_logger("GmailClient")


class GmailClient:
    """Simple Gmail API client for webhook service"""

    BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, access_token: str):
        """
        Initialize Gmail client

        Args:
            access_token: Valid Google OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        self.logger = logger

    async def fetch_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single message by ID

        Args:
            message_id: Gmail message ID

        Returns:
            Full Gmail API message response or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                message_url = f"{self.BASE_URL}/messages/{message_id}"
                params = {"format": "full"}

                response = await client.get(
                    message_url,
                    headers=self.headers,
                    params=params
                )

                if response.status_code != 200:
                    logger.error(f"Failed to fetch message: {response.status_code}", extra={'message_id': message_id})
                    return None

                return response.json()

        except Exception as e:
            logger.error(f"Error fetching message: {str(e)}", extra={'message_id': message_id}, exc_info=True)
            return None

    async def get_history(self, start_history_id: str, max_results: int = 100) -> Dict[str, Any]:
        """
        Fetch history changes since a specific history ID

        Args:
            start_history_id: History ID to start from
            max_results: Maximum number of history records

        Returns:
            Gmail history API response
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                history_url = f"{self.BASE_URL}/history"
                params = {
                    "startHistoryId": start_history_id,
                    "maxResults": max_results,
                    "historyTypes": ["messageAdded"]  # Only new messages
                }

                response = await client.get(
                    history_url,
                    headers=self.headers,
                    params=params
                )

                if response.status_code != 200:
                    logger.error(f"Failed to fetch history: {response.status_code}", extra={'start_history_id': start_history_id})
                    return {}

                return response.json()

        except Exception as e:
            logger.error(f"Error fetching history: {str(e)}", extra={'start_history_id': start_history_id}, exc_info=True)
            return {}

    async def list_recent_messages(self, max_results: int = 10) -> List[str]:
        """
        List most recent message IDs (fallback if history API fails)

        Args:
            max_results: Number of messages to fetch

        Returns:
            List of message IDs
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                list_url = f"{self.BASE_URL}/messages"
                params = {
                    "maxResults": max_results,
                    "q": "in:inbox"  # Only inbox messages
                }

                response = await client.get(
                    list_url,
                    headers=self.headers,
                    params=params
                )

                if response.status_code != 200:
                    logger.error(f"Failed to list messages: {response.status_code}")
                    return []

                data = response.json()
                messages = data.get("messages", [])
                return [msg["id"] for msg in messages]

        except Exception as e:
            logger.error(f"Error listing messages: {str(e)}", exc_info=True)
            return []
