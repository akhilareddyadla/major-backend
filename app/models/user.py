from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator
from datetime import datetime
# from bson import ObjectId  # No longer needed for API models

# PyObjectId is only for internal use, not for API models
# class PyObjectId(str):
#     @classmethod
#     def __get_validators__(cls):
#         yield cls.validate
#
#     @classmethod
#     def validate(cls, v):
#         if not ObjectId.is_valid(str(v)):
#             raise ValueError("Invalid ObjectId")
#         return str(v)

class UserBase(BaseModel):
    email: EmailStr
    username: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "username": "johndoe",
                "password": "secretpassword"
            }
        }
    )

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    id: Optional[str] = Field(None, alias="_id")
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_superuser: bool = False

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        # json_encoders={ObjectId: str}  # Not needed for API models
    )

class User(UserBase):
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_superuser: bool = False

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        # json_encoders={ObjectId: str}  # Not needed for API models
    )

    @property
    def str_id(self) -> str:
        """Return the string representation of the ID."""
        return str(self.id)

    def model_dump(self, *args, **kwargs):
        """Override model_dump method to ensure ID is properly serialized."""
        d = super().model_dump(*args, **kwargs)
        if "_id" in d:
            d["id"] = str(d.pop("_id"))
        return d

class Token(BaseModel):
    access_token: str
    token_type: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }
    )

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None

class UserSignup(BaseModel):
    email: EmailStr
    username: str
    password: str
    confirmPassword: str = Field(..., alias="confirmPassword")

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirmPassword:
            raise ValueError("Passwords do not match")
        return self

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "username": "johndoe",
                "password": "secretpassword",
                "confirmPassword": "secretpassword"
            }
        }
    ) 