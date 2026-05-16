import os
import logging

BASE_URL = "http://localhost:8007"

# Printer polling configuration
POLL_INTERVAL_MS = 30000  # Poll for jobs every 30 seconds
POLL_LIMIT = 10  # Default jobs to fetch per poll
POLL_CLAIM_JOBS = True  # Atomically claim jobs when polling

# Heartbeat configuration
HEARTBEAT_INTERVAL_MS = 30000  # Send heartbeat every 30 seconds

# API request timeout
API_TIMEOUT_SECONDS = 10

# Logging configuration
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "printer_app.log")

def setup_logging():
    """Initialize logging to both file and console."""
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
        except Exception as e:
            print(f"Error creating log directory: {e}")
            return

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True
    )

# Initialize logging immediately upon configuration load
setup_logging()
