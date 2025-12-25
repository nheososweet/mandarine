# app/core/logging.py
import logging
import sys

# Configure standard Python logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout) # Print logs to console
        ]
    )
    return logging.getLogger("rag_backend")

logger = setup_logging()