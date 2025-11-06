"""Minimal database access for webhook service"""

import os
from sqlalchemy import create_engine, Column, String, Text, TIMESTAMP
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from typing import Optional, Tuple
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import base64
from utils.logger import get_logger

load_dotenv()

logger = get_logger("Database")

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# Minimal models (read-only for webhook service)
class Person(Base):
    """Person model (read-only)"""
    __tablename__ = "persons"

    id = Column(UUID(as_uuid=True), primary_key=True)
    primary_email = Column(String(255), unique=True, nullable=False, index=True)
    primary_name = Column(String(255))


class OAuthToken(Base):
    """OAuth token model (read-write for historyId updates)"""
    __tablename__ = "oauth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True)
    person_id = Column(UUID(as_uuid=True), nullable=False)
    platform_id = Column(Text, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(TIMESTAMP, nullable=False)
    gmail_history_id = Column(Text, nullable=True)  # Last processed Gmail historyId


def get_db() -> Session:
    """Get database session"""
    return SessionLocal()


def encrypt_token(token: str) -> str:
    """
    Encrypt OAuth token

    Args:
        token: Plain token string

    Returns:
        Encrypted token
    """
    try:
        encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY")
        if not encryption_key:
            logger.warning("TOKEN_ENCRYPTION_KEY not set, returning token as-is")
            return token

        fernet = Fernet(encryption_key.encode())
        return fernet.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}", exc_info=True)
        return token


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt OAuth token

    Args:
        encrypted_token: Encrypted token string

    Returns:
        Decrypted token
    """
    try:
        encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY")
        if not encryption_key:
            logger.warning("TOKEN_ENCRYPTION_KEY not set, returning token as-is")
            return encrypted_token

        fernet = Fernet(encryption_key.encode())
        return fernet.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}", exc_info=True)
        return encrypted_token


def lookup_person_and_token(email: str, platform_id: str = "gmail_platform_001") -> Optional[Tuple[str, str, Optional[str]]]:
    """
    Lookup person_id, access_token, and last historyId by email (with auto-refresh)

    Args:
        email: User email address
        platform_id: Platform identifier

    Returns:
        Tuple of (person_id, access_token, last_history_id) or None if not found
    """
    db = get_db()

    try:
        from datetime import datetime, timedelta, timezone
        import requests
        
        # Normalize email
        email_normalized = email.lower().strip()

        # Find person by email
        person = db.query(Person).filter(Person.primary_email == email_normalized).first()

        if not person:
            logger.warning(f"Person not found for email", extra={'email': email})
            return None

        # Find OAuth token for person + platform
        token_record = db.query(OAuthToken).filter(
            OAuthToken.person_id == person.id,
            OAuthToken.platform_id == platform_id
        ).first()

        if not token_record:
            logger.warning(f"OAuth token not found", extra={'person_id': str(person.id), 'platform_id': platform_id})
            return None

        # Check if token is expired or about to expire (5 min buffer)
        now = datetime.now(timezone.utc)
        buffer_time = timedelta(minutes=5)
        
        if token_record.token_expires_at <= (now + buffer_time):
            logger.info(f"Token expired/expiring, refreshing", extra={'person_id': str(person.id)})
            
            # Refresh token
            refresh_token = decrypt_token(token_record.refresh_token)
            
            try:
                response = requests.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    new_access_token = token_data["access_token"]
                    expires_in = token_data.get("expires_in", 3600)
                    
                    # Update token in database
                    expires_at = now + timedelta(seconds=expires_in)
                    encrypted_token = encrypt_token(new_access_token)
                    
                    token_record.access_token = encrypted_token
                    token_record.token_expires_at = expires_at
                    db.commit()
                    
                    logger.info(f"Token refreshed successfully", extra={'person_id': str(person.id)})
                    access_token = new_access_token
                else:
                    logger.error(f"Token refresh failed: {response.status_code}", extra={'person_id': str(person.id)})
                    access_token = decrypt_token(token_record.access_token)
            except Exception as e:
                logger.error(f"Error refreshing token: {str(e)}", extra={'person_id': str(person.id)}, exc_info=True)
                access_token = decrypt_token(token_record.access_token)
        else:
            # Token is still valid
            access_token = decrypt_token(token_record.access_token)
            # Removed verbose "Found person" message
        
        # Get last historyId
        last_history_id = token_record.gmail_history_id if token_record.gmail_history_id else None

        return str(person.id), access_token, last_history_id

    except Exception as e:
        logger.error(f"Error looking up person: {str(e)}", extra={'email': email}, exc_info=True)
        return None

    finally:
        db.close()


def update_gmail_history_id(person_id: str, platform_id: str, history_id: str) -> bool:
    """
    Update the last processed Gmail historyId for a person
    
    Args:
        person_id: Person UUID
        platform_id: Platform identifier
        history_id: New historyId to store
        
    Returns:
        True if updated successfully, False otherwise
    """
    db = get_db()
    
    try:
        import uuid as uuid_lib
        
        # Convert person_id to UUID
        person_uuid = uuid_lib.UUID(person_id)
        
        # Find token record
        token_record = db.query(OAuthToken).filter(
            OAuthToken.person_id == person_uuid,
            OAuthToken.platform_id == platform_id
        ).first()
        
        if not token_record:
            logger.warning(f"Token record not found", extra={'person_id': person_id})
            return False
        
        # Update historyId
        token_record.gmail_history_id = history_id
        db.commit()
        
        # Removed verbose "Updated historyId" message - too verbose
        return True
        
    except Exception as e:
        logger.error(f"Error updating historyId: {str(e)}", extra={'person_id': person_id, 'history_id': history_id}, exc_info=True)
        db.rollback()
        return False
        
    finally:
        db.close()
