from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 