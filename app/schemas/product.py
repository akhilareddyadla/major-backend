from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1)
    current_price: float = Field(..., gt=0)
    target_price: float = Field(..., gt=0)
    description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False

    class Config:
        from_attributes = True 