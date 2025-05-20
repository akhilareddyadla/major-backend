from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class AlertBase(BaseModel):
    product_id: str
    target_price: float = Field(..., gt=0)
    is_active: bool = True
    notification_type: str = Field(..., pattern="^(email|push|both)$")

class AlertCreate(AlertBase):
    pass

class AlertResponse(AlertBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    triggered_at: Optional[datetime] = None

    class Config:
        from_attributes = True 