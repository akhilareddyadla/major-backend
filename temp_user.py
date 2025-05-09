from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDB(UserBase):
    id: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    is_superuser: bool = False
    model_config = ConfigDict(from_attributes=True)

class User(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    is_superuser: bool
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str
    model_config = ConfigDict(from_attributes=True)

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: int
    model_config = ConfigDict(from_attributes=True) 