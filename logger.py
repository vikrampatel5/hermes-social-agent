import json
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path

class Logger:
    def __init__(self, log_path: str = "/home/opc/hermes-social-agent/logs", level: str = "INFO"):
        self.log_path = Path(log_path)
        self.log_path.mkdir(parents=True, exist_ok=True)
        self.level = level
        self.levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    
    def _write(self, level: str, message: str, **kwargs):
        if self.levels.get(level, 1) < self.levels.get(self.level, 1):
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        extra = ""
        if kwargs:
            extra = " | " + " ".join(f"{k}={v}" for k, v in kwargs.items())
        
        log_line = f"[{timestamp}] [{level}] {message}{extra}"
        print(log_line)
        
        # Write to file
        log_file = self.log_path / f"{level.lower()}.log"
        with open(log_file, "a") as f:
            f.write(log_line + "\n")
    
    def debug(self, message: str, **kwargs):
        self._write("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._write("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._write("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._write("ERROR", message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._write("CRITICAL", message, **kwargs)
    
    def discovery(self, platform: str, query: str, results: int):
        self.info("DISCOVERY", platform=platform, query=query, results=results)
    
    def analysis(self, content_id: int, relevance: int, fit: int, spam_risk: int, decision: str):
        self.info("ANALYSIS", content_id=content_id, relevance=relevance, fit=fit, spam_risk=spam_risk, decision=decision)
    
    def comment(self, strategy: str, length: int, quality_score: int):
        self.info("COMMENT", strategy=strategy, length=length, quality_score=quality_score)
    
    def post(self, platform: str, status: str):
        self.info("POST", platform=platform, status=status)
    
    def tracking(self, clicks: int, signups: int):
        self.info("TRACKING", clicks=clicks, signups=signups)
    
    def learning(self, strategy: str, signup_rate: float, decision: str):
        self.info("LEARNING", strategy=strategy, signup_rate=signup_rate, decision=decision)