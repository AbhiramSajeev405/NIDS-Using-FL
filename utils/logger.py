"""
LSCUDAPORT - Logging Utility
Proper logging to replace print statements (Fixes BUG #012).
"""

import logging
import sys
from pathlib import Path

# Create logger
logger = logging.getLogger('lscudaport')
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

# File handler (optional)
try:
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "lscudaport.log")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
except Exception:
    pass  # Can't create log file, continue with console only

# Add console handler
logger.addHandler(console_handler)

def get_logger(name):
    """Get a child logger for a specific module.

    Usage:
        from utils.logger import get_logger
        logger = get_logger('client')
        logger.info("Training started")
        logger.error("Connection failed")
    """
    return logger.getChild(name)
