"""Logger factory and context helpers for structured logging"""

import logging
from typing import Optional


def get_logger(service_name: str) -> logging.Logger:
    """
    Get a logger with service name automatically included in messages
    
    Args:
        service_name: Service name to include in log messages (e.g., "Webhook", "GmailClient")
    
    Returns:
        Logger instance configured with service name
    """
    logger = logging.getLogger(service_name)
    
    # Create a custom adapter that adds service name and context to messages
    class ServiceLoggerAdapter(logging.LoggerAdapter):
        def __init__(self, logger, service_name):
            super().__init__(logger, {'service_name': service_name})
            self.service_name = service_name
        
        def process(self, msg, kwargs):
            # Format: [SERVICE] [CONTEXT] message
            context_parts = []
            extra = kwargs.get('extra', {})
            
            if 'person_id' in extra:
                person_id = str(extra['person_id'])
                context_parts.append(f"[person_id={person_id[:8] if len(person_id) > 8 else person_id}]")
            if 'request_id' in extra:
                context_parts.append(f"[request_id={extra['request_id']}]")
            if 'message_id' in extra:
                message_id = str(extra['message_id'])
                context_parts.append(f"[message_id={message_id[:8] if len(message_id) > 8 else message_id}]")
            if 'history_id' in extra:
                context_parts.append(f"[history_id={extra['history_id']}]")
            if 'email' in extra:
                email = str(extra['email'])
                context_parts.append(f"[email={email[:20] if len(email) > 20 else email}]")
            
            context_str = ' '.join(context_parts)
            formatted_msg = f"[{self.service_name}]"
            if context_str:
                formatted_msg += f" {context_str}"
            formatted_msg += f" {msg}"
            
            return formatted_msg, kwargs
    
    return ServiceLoggerAdapter(logger, service_name)

