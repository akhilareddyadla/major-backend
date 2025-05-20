from fastapi import APIRouter
from app.api.api_v1.endpoints import auth, users, products, alerts, notifications  # Include all routers

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

# This file is intentionally left empty to mark the directory as a Python package