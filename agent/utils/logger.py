import re
import logging
from typing import Optional

# Setup standard logger
logger: logging.Logger = logging.getLogger("ai_automation_tester")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler: logging.Handler = logging.StreamHandler()
    formatter: logging.Formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def mask_text(text: str, password_to_mask: Optional[str] = None) -> str:
    """Masks cleartext passwords in strings to ensure security and compliance."""
    if not text:
        return text

    masked: str = text
    if password_to_mask and password_to_mask.strip():
        masked = masked.replace(password_to_mask, "******")

    # Regex fallback for password patterns
    pattern = re.compile(r'(password[:=\s]+)(["\']?[^\s,"\'&]+["\']?)', re.IGNORECASE)
    masked = pattern.sub(r'\1******', masked)
    return masked

def log_info(msg: str, password_to_mask: Optional[str] = None) -> None:
    """Logs an informational message with masked credentials."""
    logger.info(mask_text(msg, password_to_mask))

def log_error(msg: str, password_to_mask: Optional[str] = None) -> None:
    """Logs an error message with masked credentials."""
    logger.error(mask_text(msg, password_to_mask))

def log_warning(msg: str, password_to_mask: Optional[str] = None) -> None:
    """Logs a warning message with masked credentials."""
    logger.warning(mask_text(msg, password_to_mask))
