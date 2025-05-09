# Price Drop Alert System

A FastAPI-based backend system for tracking product prices and sending alerts when prices drop.

## Features

- User authentication and management
- Product tracking and price monitoring
- Web scraping for multiple e-commerce sites
- Price history visualization
- Email and WebSocket notifications
- MongoDB data storage

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:
```
MONGODB_URL=mongodb://localhost:27017
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
SMTP_SERVER=your-smtp-server
SMTP_PORT=587
SMTP_USERNAME=your-email
SMTP_PASSWORD=your-password
```

4. Run the application:
```bash
uvicorn app.main:app --reload
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
app/
├── api/           # API routes
├── core/          # Core functionality
├── db/            # Database models and connections
├── models/        # Pydantic models
├── schemas/       # Database schemas
├── services/      # Business logic
├── utils/         # Utility functions
└── main.py        # Application entry point
``` 