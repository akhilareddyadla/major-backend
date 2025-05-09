from fastapi import APIRouter, Form, HTTPException
from app.models.product import ProductResponse
from app.db.mongodb import get_collection
from typing import Optional, List
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/products", response_model=ProductResponse)
async def add_product(
    name: str = Form(...),
    url: str = Form(...),
    website: str = Form(...),
    currency: str = Form(...),
    current_price: float = Form(...),
    target_price: float = Form(...),
    price_drop_threshold: float = Form(...),
    category: str = Form(...),
    image_url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    # Log incoming request
    logger.info(f"Processing add_product request: name={name}, url={url}, website={website}")
    
    # Prepare product data
    product_data = {
        "name": name,
        "url": url,
        "website": website,
        "currency": currency,
        "current_price": current_price,
        "target_price": target_price,
        "price_drop_threshold": price_drop_threshold,
        "category": category,
        "image_url": image_url,
        "description": description,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    try:
        # Insert into MongoDB
        products_collection = get_collection("products")
        result = await products_collection.insert_one(product_data)
        product_data["id"] = str(result.inserted_id)
        logger.info(f"Product added successfully with ID: {product_data['id']}")
        return ProductResponse(**product_data)
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/products", response_model=List[ProductResponse])
async def get_products():
    logger.info("Processing get_products request")
    try:
        products_collection = get_collection("products")
        products = await products_collection.find().to_list(None)
        # Convert MongoDB documents to ProductResponse format
        for product in products:
            product["id"] = str(product["_id"])  # Convert ObjectId to string
            del product["_id"]  # Remove the MongoDB _id field
        logger.info(f"Successfully fetched {len(products)} products")
        return products
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")