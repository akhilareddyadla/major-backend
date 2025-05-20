from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class NotificationBase(BaseModel):
    title: str
    message: str
    type: str
    data: Optional[Dict[str, Any]] = None

class NotificationCreate(NotificationBase):
    user_id: str

class NotificationResponse(NotificationBase):
    id: str
    user_id: str
    created_at: datetime
    is_read: bool
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True 