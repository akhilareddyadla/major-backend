from pydantic_settings import BaseSettings
from typing import List, Optional, Union
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Price Tracker API"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "API for tracking product prices across multiple e-commerce platforms"
    API_V1_STR: str = "/api/v1"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # MongoDB Settings
    MONGODB_URL: str
    DATABASE_NAME: str = "price_tracker"
    MONGODB_NAME: str = "price_alerts"
    
    # Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SECURITY_BCRYPT_ROUNDS: int = 12
    SECURITY_PASSWORD_SALT: str = os.getenv("SECURITY_PASSWORD_SALT", "your-salt-here")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-jwt-secret-key-here")
    JWT_ALGORITHM: str = "HS256"
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Scheduler Settings
    SCHEDULER_TIMEZONE: str = "UTC"
    PRICE_CHECK_INTERVAL: int = 60  # minutes
    SCRAPING_INTERVAL_MINUTES: int = 60  # Added to match .env

    # Email Settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_TLS: bool = True
    EMAILS_FROM_EMAIL: str = os.getenv("EMAILS_FROM_EMAIL", "")
    EMAILS_FROM_NAME: str = os.getenv("EMAILS_FROM_NAME", "Price Tracker")

    # Twilio Settings
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER_SMS: str = os.getenv("TWILIO_FROM_NUMBER_SMS", "")
    TWILIO_FROM_NUMBER_WHATSAPP: str = os.getenv("TWILIO_FROM_NUMBER_WHATSAPP", "")

    # Apify Settings
    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")

    def get_mongodb_url(self) -> str:
        """Get properly formatted MongoDB URL."""
        if self.MONGODB_URL.startswith("mongodb://") or self.MONGODB_URL.startswith("mongodb+srv://"):
            return self.MONGODB_URL
        return f"mongodb://{self.MONGODB_URL}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra fields from .env file

settings = Settings() 