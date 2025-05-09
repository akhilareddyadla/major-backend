from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from enum import Enum
from bson import ObjectId

class WebsiteType(str, Enum):
    AMAZON = "amazon"
    FLIPKART = "flipkart"
    EBAY = "ebay"
    MEESHO = "meesho"
    OTHER = "other"

class CurrencyType(str, Enum):
    USD = "USD"
    INR = "INR"

class AlertType(str, Enum):
    PRICE_DROP = "price_drop"
    DISCOUNT = "discount"
    STOCK = "stock"
    PRICE_INCREASE = "price_increase"

class ProductBase(BaseModel):
    name: str = Field(..., example="iPhone 15 Pro")
    url: HttpUrl
    website: str
    currency: str
    current_price: float
    target_price: float
    price_drop_threshold: float
    category: str
    image_url: Optional[HttpUrl] = None
    description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductInDB(ProductBase):
    id: str
    created_at: datetime
    updated_at: datetime
    image_path: Optional[str] = None  # For uploaded files

class ProductResponse(ProductInDB):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    website_type: Optional[WebsiteType] = None
    current_price: Optional[float] = None
    desired_price: Optional[float] = None
    currency: Optional[CurrencyType] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    alert_threshold: Optional[int] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class Product(BaseModel):
    id: str = Field(default_factory=str, alias="_id")
    user_id: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None
    website_type: Optional[WebsiteType] = None
    current_price: Optional[float] = None
    desired_price: Optional[float] = None
    currency: Optional[CurrencyType] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    alert_threshold: Optional[int] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    is_favorite: Optional[bool] = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    price_history: Optional[List[dict]] = []

class PriceHistory(BaseModel):
    price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    currency: CurrencyType = Field(default=CurrencyType.INR)
    is_discount: bool = Field(default=False)

class AlertPreferenceCreate(BaseModel):
    user_id: str
    product_id: str
    alert_type: AlertType
    threshold: float
    is_active: bool = True
    notification_method: str = "email"

class AlertPreferenceUpdate(BaseModel):
    alert_type: Optional[AlertType] = None
    threshold: Optional[float] = None
    is_active: Optional[bool] = None
    notification_method: Optional[str] = None

class AlertPreference(BaseModel):
    id: str = Field(default_factory=str, alias="_id")
    user_id: str
    product_id: str
    alert_type: AlertType
    threshold: float
    is_active: bool
    notification_method: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PriceDropAlert(BaseModel):
    id: str = Field(default_factory=str, alias="_id")
    user_id: str
    product_id: str
    old_price: float
    new_price: float
    price_drop_percentage: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DiscountAlert(BaseModel):
    id: str = Field(default_factory=str, alias="_id")
    user_id: str
    product_id: str
    discount_percentage: float
    created_at: datetime = Field(default_factory=datetime.utcnow)