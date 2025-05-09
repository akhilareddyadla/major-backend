from pydantic_settings import BaseSettings
from typing import List, Optional, Union
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Application settings
    PROJECT_NAME: str = "Price Tracker API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API for tracking product prices"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    # Server settings
    HOST: str = os.getenv("HOST", "127.0.0.1")  # Changed from 0.0.0.0 to 127.0.0.1 for local development
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # MongoDB settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "price_tracker")
    MONGODB_NAME: str = os.getenv("MONGODB_NAME", "price_tracker")  # Added for compatibility
    
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-at-least-32-characters")  # Added missing field
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-at-least-32-characters-long")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")  # Added missing field
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    
    # Security settings
    SECURITY_BCRYPT_ROUNDS: int = int(os.getenv("SECURITY_BCRYPT_ROUNDS", "12"))
    SECURITY_PASSWORD_SALT: str = os.getenv("SECURITY_PASSWORD_SALT", "your-salt-at-least-8-characters")
    
    # Email settings
    SMTP_TLS: bool = True
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAILS_FROM_EMAIL: str = os.getenv("EMAILS_FROM_EMAIL", "")
    EMAILS_FROM_NAME: str = os.getenv("PROJECT_NAME", PROJECT_NAME)
    
    # Scheduler settings
    SCHEDULER_TIMEZONE: str = "UTC"
    PRICE_CHECK_INTERVAL: int = int(os.getenv("PRICE_CHECK_INTERVAL", "3600"))  # in seconds
    SCRAPING_INTERVAL_MINUTES: int = int(os.getenv("SCRAPING_INTERVAL_MINUTES", "60"))  # in minutes

    # Scraper settings
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "extra": "allow"
    }

settings = Settings() 