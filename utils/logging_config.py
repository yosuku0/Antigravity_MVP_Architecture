import logging
from logging.handlers import RotatingFileHandler
import json
import time
from pathlib import Path

class JSONLFormatter(logging.Formatter):
    """JSONL format with optional job_id support."""
    def format(self, record):
        log_record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        # Add job_id if provided via extra={'job_id': '...'}
        if hasattr(record, "job_id"):
            log_record["job_id"] = record.job_id
        
        # Include exception info if available
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record, ensure_ascii=False)

def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # 1. Console Handler (Human-readable)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(ch)
        
        # 2. Rotating File Handler (JSONL)
        log_file = Path("work/system.jsonl")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 10MB x 5 generations
        fh = RotatingFileHandler(
            log_file, 
            maxBytes=10 * 1024 * 1024, 
            backupCount=5, 
            encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(JSONLFormatter())
        logger.addHandler(fh)
        
    return logger

def reset_logging(name: str):
    """Clear handlers for a logger (useful for tests)."""
    logger = logging.getLogger(name)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
