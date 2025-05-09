from fastapi import APIRouter

router = APIRouter(
    prefix="/auth",
    tags=["auth", "social"]
)

# Social login endpoints have been removed as per user request. 