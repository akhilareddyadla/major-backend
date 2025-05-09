from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import logging
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.core.config import settings
from app.services.alerts import alert_service
from app.services.products import product_service
from app.services.auth import auth_service
from app.services.notification import notification_service
from app.db.init_db import init_db
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from app.api.api_v1.api import api_router
import json
from typing import Dict
from fastapi.websockets import WebSocketState
import uvicorn
from starlette.routing import Route, WebSocketRoute

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        routes=app.routes,
    )

    # Add security schemes
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
        
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    expose_headers=["Content-Type", "Authorization"],
)

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

@app.websocket(f"{settings.API_V1_STR}/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected successfully"
        })
        
        # Keep connection alive with ping/pong
        while True:
            try:
                # Wait for message
                data = await websocket.receive_text()
                logger.debug(f"Received WebSocket message: {data}")
                
                # Process message
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    else:
                        # Process other message types
                        await websocket.send_json({
                            "type": "message_received",
                            "message": "Message processed successfully"
                        })
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON message")
                    continue
                    
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except:
            pass

# Add error handling middleware
@app.middleware("http")
async def add_error_handling(request, call_next):
    try:
        # Log incoming request
        logger.debug(f"Incoming request: {request.method} {request.url}")
        
        # Let the CORS middleware handle OPTIONS requests
        response = await call_next(request)
        
        # Log response status
        logger.debug(f"Response status: {response.status_code}")
        return response
        
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred"}
        )

# Include the api_router from api.py
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        logger.info("Connecting to MongoDB...")
        await connect_to_mongo()
        logger.info("MongoDB connection established")

        logger.info("Initializing database...")
        await init_db()
        logger.info("Database initialized")

        # Initialize services
        logger.info("Initializing services...")
        await auth_service.initialize()
        await product_service.initialize()
        await alert_service.initialize()
        await notification_service.initialize()
        
        logger.info("All services initialized successfully")
        
        # Log all registered routes, handling WebSocket routes
        logger.info("Registered routes:")
        for route in app.routes:
            if isinstance(route, Route):
                logger.info(f"Route: {route.path} - Methods: {route.methods}")
            elif isinstance(route, WebSocketRoute):
                logger.info(f"WebSocket Route: {route.path}")
            else:
                logger.info(f"Other Route: {route.path}")
        
    except Exception as e:
        logger.error(f"Critical error during startup: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        await close_mongo_connection()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Price Tracker API"}

if __name__ == "__main__":
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )