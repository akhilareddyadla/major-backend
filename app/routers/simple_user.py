from fastapi import APIRouter, Depends, HTTPException
from app.models.user import User, UserCreate
from app.db.mongodb import get_database
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/simple-users", tags=["simple-users"])

async def get_db():
    return get_database()

@router.post("/", response_model=User)
async def create_user(user: UserCreate, db=Depends(get_db)):
    user_dict = user.dict()
    user_dict["hashed_password"] = user_dict.pop("password")  # Simplify for example
    user_dict["created_at"] = user_dict["updated_at"] = datetime.utcnow()
    try:
        result = await db["users"].insert_one(user_dict)
        user_dict["id"] = str(result.inserted_id)
        return User(**user_dict)
    except Exception as e:
        raise HTTPException(400, f"User creation failed: {str(e)}")

@router.get("/{id}", response_model=User)
async def get_user(id: str, db=Depends(get_db)):
    try:
        user = await db["users"].find_one({"_id": ObjectId(id)})
        if not user:
            raise HTTPException(404, "User not found")
        user["id"] = str(user["_id"])
        return User(**user)
    except ValueError:
        raise HTTPException(400, "Invalid user ID") 