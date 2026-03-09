"""
Logging Configuration for HPC Data Preprocessing Pipeline
Captures detailed execution logs for each backend and stage
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Timestamp for log filename
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_FILE = LOG_DIR / f"pipeline_{TIMESTAMP}.log"

# Define log format
LOG_FORMAT = '%(asctime)s [%(levelname)8s] %(name)-30s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logging():
    """Setup logging configuration for the entire application"""
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Setup file handler (write to file)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Setup console handler (print to terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup info
    root_logger.info("="*80)
    root_logger.info("HPC Data Preprocessing Pipeline - Execution Started")
    root_logger.info("="*80)
    root_logger.info(f"Log file: {LOG_FILE}")
    root_logger.info(f"="*80)
    
    return root_logger

def get_logger(name):
    """Get logger for a specific module"""
    return logging.getLogger(name)

# Initialize logging when module is imported
root_logger = setup_logging()
