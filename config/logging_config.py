"""Centralized logging configuration for Gmail Webhook Service"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional, Tuple


def setup_logging(log_level: Optional[str] = None, log_dir: Optional[str] = None):
    """
    Setup logging configuration with rotating file handlers
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO
        log_dir: Directory for log files. Defaults to "logs"
    """
    # Get configuration from environment or parameters
    level = log_level or os.getenv('LOG_LEVEL', 'INFO')
    log_directory = log_dir or os.getenv('LOG_DIR', 'logs')
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_directory)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Main log file path
    main_log_file = log_path / "gmail_webhook.log"
    error_log_file = log_path / "gmail_webhook_errors.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create custom formatter that adds service prefixes
    class ServiceFormatter(logging.Formatter):
        def format(self, record):
            # Service name is already added by logger adapter, just format normally
            return super().format(record)
    
    # Create formatter
    # Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [SERVICE] [CONTEXT] message
    formatter = ServiceFormatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Main log handler - all levels
    main_handler = logging.handlers.RotatingFileHandler(
        main_log_file,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    main_handler.setLevel(logging.DEBUG)  # Capture all levels
    main_handler.setFormatter(formatter)
    root_logger.addHandler(main_handler)
    
    # Error log handler - ERROR level only
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)  # Only ERROR level
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Optional: Console handler for development
    if os.getenv('LOG_TO_CONSOLE', 'false').lower() == 'true':
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def get_log_file_paths() -> Tuple[Path, Path]:
    """
    Get paths to main and error log files
    
    Returns:
        Tuple of (main_log_path, error_log_path)
    """
    log_directory = os.getenv('LOG_DIR', 'logs')
    log_path = Path(log_directory)
    return (
        log_path / "gmail_webhook.log",
        log_path / "gmail_webhook_errors.log"
    )

