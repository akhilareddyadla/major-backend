from pydantic import BaseModel, Field, validator, GetJsonSchemaHandler
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from enum import Enum
from pydantic.json_schema import JsonSchemaValue
from .product import PyObjectId, AlertType

# ... rest of the file remains unchanged ... 

class Config:
    arbitrary_types_allowed = True
    json_encoders = {ObjectId: str}
    json_schema_extra = {
        "example": {
            "user_id": "user123",
            "type": "PRICE_DROP",
            "priority": "HIGH",
            "title": "Price Drop Alert",
            "message": "The price of your tracked product has dropped!",
            "channels": ["EMAIL", "IN_APP"],
            "status": "PENDING",
            "is_read": False
        }
    }

class NotificationPreference(BaseModel):
    # ... fields remain unchanged ...

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "email_enabled": True,
                "sms_enabled": False,
                "whatsapp_enabled": False,
                "push_enabled": True,
                "in_app_enabled": True,
                "quiet_hours_start": 22,
                "quiet_hours_end": 7,
                "min_price_drop_percentage": 5.0
            }
        }

class NotificationTemplate(BaseModel):
    # ... fields remain unchanged ...

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "type": "PRICE_DROP",
                "title_template": "Price Drop Alert: {product_name}",
                "message_template": "The price of {product_name} has dropped by {percentage_drop}%! New price: {current_price} {currency}",
                "priority": "HIGH",
                "channels": ["EMAIL", "IN_APP"]
            }
        } 