from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal

class PriceHistory(BaseModel):
    """Model for price history entries."""
    id: Optional[str] = Field(None, alias="_id")
    product_id: str
    price: Decimal
    currency: str = "INR"
    timestamp: datetime
    discount_percentage: Optional[float] = None
    is_discount: bool = False
    source: str = "manual"

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }
        populate_by_name = True

class PriceHistoryEntry(BaseModel):
    """Model for a single price history entry."""
    product_id: str
    price: Decimal
    currency: str = "INR"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    discount_percentage: Optional[float] = None
    is_discount: bool = False
    source: Optional[str] = None  # Where the price was found (e.g., "amazon", "flipkart")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "123",
                "price": "34999.00",
                "currency": "INR",
                "timestamp": "2024-04-30T12:00:00Z",
                "discount_percentage": 15.0,
                "is_discount": True,
                "source": "amazon"
            }
        }

class PriceHistoryCreate(PriceHistoryEntry):
    """Model for creating a new price history entry."""
    pass

class PriceHistory(PriceHistoryEntry):
    """Model for a price history entry from the database."""
    id: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "product_id": "123",
                "price": "34999.00",
                "currency": "INR",
                "timestamp": "2024-04-30T12:00:00Z",
                "discount_percentage": 15.0,
                "is_discount": True,
                "source": "amazon"
            }
        }

class EnhancedPriceHistory(BaseModel):
    price_change_percentage: float
    trend: str
    change_frequency: dict
    price_points: list[PriceHistory]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 