from fastapi import APIRouter
from app.api.api_v1.endpoints import users, auth, alerts, websocket
from app.api.api_v1.endpoints.products import router as products_router

# Create main API router with version prefix
api_router = APIRouter(prefix="/api/v1")

# Mount WebSocket router
api_router.include_router(
    websocket.router,
    prefix="/ws",
    tags=["websocket"]
)

# Mount other routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)
api_router.include_router(
    products_router,
    prefix="/products",
    tags=["products"]
)
api_router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["alerts"]
)