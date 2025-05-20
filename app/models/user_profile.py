from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class NotificationMethod(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"

class AlertFrequency(str, Enum):
    REAL_TIME = "real_time"
    DAILY = "daily"
    WEEKLY = "weekly"

class UserPreferences(BaseModel):
    preferred_categories: List[str]
    preferred_brands: List[str]
    min_price: float
    max_price: float
    notification_methods: List[NotificationMethod]
    alert_frequency: AlertFrequency

class WatchlistItem(BaseModel):
    product_id: str
    product_name: str
    desired_price: float
    current_price: float
    platform: str
    added_date: datetime

class InteractionHistory(BaseModel):
    recently_viewed: List[str]  # List of product IDs
    search_history: List[str]   # List of search queries
    clicked_alerts: List[str]   # List of alert IDs

class UserProfile(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone_number: str = Field(pattern=r'^\+?1?\d{9,15}$')
    preferences: UserPreferences
    watchlist: List[WatchlistItem]
    interaction_history: InteractionHistory
    created_at: datetime
    updated_at: datetime

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(default=None, pattern=r'^\+?1?\d{9,15}$')
    preferences: Optional[UserPreferences] = None 