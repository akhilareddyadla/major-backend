from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, HttpUrl, Field, validator, GetJsonSchemaHandler
from decimal import Decimal
from enum import Enum
from bson import ObjectId
from pydantic.json_schema import JsonSchemaValue

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema, _handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        return {"type": "string", "description": "ObjectId"}

class WebsiteType(str, Enum):
    AMAZON = "amazon"
    EBAY = "ebay"
    WALMART = "walmart"
    CUSTOM = "custom"

class AlertType(str, Enum):
    PRICE_DROP = "PRICE_DROP"
    PRICE_INCREASE = "PRICE_INCREASE"
    TARGET_REACHED = "TARGET_REACHED"
    STOCK_ALERT = "STOCK_ALERT"

class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"

class ProductBase(BaseModel):
    name: str
    url: HttpUrl
    website_type: WebsiteType = WebsiteType.AMAZON
    current_price: Decimal
    target_price: Decimal
    currency: str = "INR"
    price_drop_threshold: float = 10.0
    image_url: Optional[HttpUrl] = None
    description: Optional[str] = None
    category: Optional[str] = None
    comparison_prices: Optional[Dict[str, Optional[float]]] = None  # Added field

class ProductCreate(BaseModel):
    url: HttpUrl
    target_price: float = Field(gt=0, description="Target price must be greater than 0")
    user_id: str
    title: Optional[str] = None
    asin: Optional[str] = None
    priority: Optional[int] = Field(default=1, ge=1, le=5, description="Priority level from 1 to 5")
    check_frequency: Optional[int] = Field(default=24, ge=1, le=24, description="Hours between price checks")

    @validator('target_price')
    def validate_target_price(cls, v):
        if v <= 0:
            raise ValueError("Target price must be greater than 0")
        return round(v, 2)

class ProductUpdate(BaseModel):
    target_price: Optional[float] = Field(gt=0)
    priority: Optional[int] = Field(ge=1, le=5)
    check_frequency: Optional[int] = Field(ge=1, le=24)
    status: Optional[ProductStatus]
    is_active: Optional[bool]

    @validator('target_price')
    def validate_target_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Target price must be greater than 0")
        return round(v, 2) if v is not None else v

class PriceHistory(BaseModel):
    price: float
    currency: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str

class Product(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    url: HttpUrl
    target_price: float
    user_id: str
    title: Optional[str] = None
    asin: Optional[str] = None
    current_price: Optional[float] = None
    currency: Optional[str] = "INR"
    priority: int = Field(default=1, ge=1, le=5)
    check_frequency: int = Field(default=24, ge=1, le=24)
    status: ProductStatus = Field(default=ProductStatus.ACTIVE)
    is_active: bool = Field(default=True)
    price_history: List[PriceHistory] = Field(default_factory=list)
    last_checked: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "url": "https://www.amazon.in/product/123",
                "target_price": 999.99,
                "user_id": "user123",
                "title": "Sample Product",
                "asin": "B07XYZ123",
                "current_price": 1299.99,
                "currency": "INR",
                "priority": 1,
                "check_frequency": 24,
                "status": "active",
                "is_active": True
            }
        }

class Alert(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    product_id: str
    alert_type: AlertType
    message: str
    data: Dict[str, Any]
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class PriceDropAlert(Alert):
    product_name: str
    product_url: HttpUrl
    original_price: float
    current_price: float
    price_drop: float
    percentage_drop: float

    @validator('price_drop', 'percentage_drop')
    def validate_price_drop(cls, v, values):
        if v < 0:
            raise ValueError("Price drop and percentage drop must be positive")
        return v

    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "product_id": "product123",
                "alert_type": "PRICE_DROP",
                "product_name": "Sample Product",
                "product_url": "https://www.amazon.in/product/123",
                "original_price": 1299.99,
                "current_price": 999.99,
                "price_drop": 300.00,
                "percentage_drop": 23.08
            }
        }

class AlertPreference(BaseModel):
    user_id: str
    product_id: str
    alert_type: str  # e.g., "price_drop", "discount"
    threshold: Optional[float] = None
    is_active: bool = True

class DiscountAlert(BaseModel):
    user_id: str
    product_id: str
    discount_percentage: float
    is_active: bool = True

class AlertPreferenceCreate(BaseModel):
    product_id: str
    alert_type: str  # e.g., "price_drop", "discount"
    threshold: Optional[float] = None
    percentage_drop: Optional[float] = None
    notification_channels: Optional[List[str]] = None
    frequency: Optional[str] = None
    custom_message: Optional[str] = None

class AlertPreferenceUpdate(BaseModel):
    threshold: Optional[float] = None
    percentage_drop: Optional[float] = None
    notification_channels: Optional[List[str]] = None
    frequency: Optional[str] = None
    custom_message: Optional[str] = None
    is_active: Optional[bool] = None

class ProductResponse(BaseModel):
    id: str
    name: str
    url: str
    website: str
    category: Optional[str] = None
    current_price: Optional[float] = None
    target_price: Optional[float] = None
    price_drop_threshold: Optional[float] = None
    image_url: Optional[str] = None
    # Add other fields as needed for display, e.g., prices from different sites
    amazon_price: Optional[str] = None
    flipkart_price: Optional[str] = None
    reliance_digital_price: Optional[str] = None

    class Config:
        orm_mode = True