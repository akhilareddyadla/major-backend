from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app.models.product import Product, ProductCreate, ProductUpdate, PriceHistory
from app.services.products import product_service
from app.services.auth import auth_service
from app.services.apify import ApifyAmazonScraper
from app.core.config import settings
from app.db.mongodb import get_database
from datetime import datetime
import logging
import re
from app.services.price_extractor import price_extractor  # Import the singleton instance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["products"])

# Initialize Apify scraper (kept for potential future use, but we'll primarily use price_extractor)
apify_scraper = ApifyAmazonScraper(settings.APIFY_API_TOKEN)

def parse_bool(value: Optional[str] = Query(None, description="Filter by active status (true/false)")) -> Optional[bool]:
    if value is None:
        return None
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise ValueError("Invalid boolean value for is_active")

@router.post("/", response_model=Product)
async def add_product(
    product: ProductCreate,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Create a new product and fetch its details from multiple platforms."""
    try:
        # Fetch prices from all supported platforms using price_extractor
        prices = price_extractor.get_product_details(product.url)
        
        # Determine the price based on the product's website
        platform_key = product.website.lower()
        if platform_key == "reliance digital":
            platform_key = "reliancedigital"
        elif platform_key not in ["amazon", "flipkart"]:
            platform_key = None

        if not platform_key or prices.get(platform_key, "Not found") == "Not found":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not fetch a valid price for the specified website: {product.website}"
            )

        current_price = prices[platform_key]
        # Clean the price (remove currency symbol and commas for storage)
        try:
            current_price = float(re.sub(r'[^\d.]', '', current_price))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid price format fetched for {product.website}: {current_price}"
            )

        # Validate the price
        if current_price < 1000:  # Arbitrary threshold for validation
            logger.warning(f"Price {current_price} for {product.website} seems unrealistically low.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Price {current_price} for {product.website} seems unrealistically low."
            )

        # Extract title from the price_extractor response (we'll need to modify price_extractor to return the title)
        # For now, we'll assume a title is available; you may need to adjust based on your price_extractor's return value
        # Since price_extractor doesn't return the title directly, we'll fetch it separately if needed
        # Alternatively, modify price_extractor to return the title along with prices
        title = product.name  # Fallback to the provided name; ideally, fetch from price_extractor

        # Prepare product data
        product_data = product.dict()
        product_data.update({
            "user_id": str(current_user.id),
            "title": title,
            "current_price": current_price,
            "currency": "INR",  # Hardcoding to INR since price_extractor uses ₹
            "url": product.url,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "is_favorite": False
        })
        
        # Save to database
        db = get_database()
        result = await db.products.insert_one(product_data)
        product_data["_id"] = result.inserted_id
        
        return Product(**product_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding product: {str(e)}"
        )

@router.get("/fetch-price/")
async def fetch_product_price(
    url: str = Query(..., description="The URL of the product to fetch price for"),
    current_user = Depends(auth_service.get_current_active_user)
):
    """Fetch the current price of a product from supported platforms."""
    try:
        if not url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product URL is required"
            )

        # Use the price_extractor to fetch prices
        prices = price_extractor.get_product_details(url)

        # Basic validation: Check if any price is unrealistically low
        for platform, price in prices.items():
            if price != "Not found" and isinstance(price, str):
                try:
                    # Extract numeric value from formatted price (e.g., "₹7.55" -> 7.55)
                    price_value = float(re.sub(r'[^\d.]', '', price))
                    if price_value < 1000:  # Arbitrary threshold for validation
                        logger.warning(f"Price {price_value} for {platform} seems unrealistically low.")
                        prices[platform] = "Invalid price detected"
                except ValueError:
                    prices[platform] = "Invalid price format"

        return prices
    except Exception as e:
        logger.error(f"Error fetching product price: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching product price: {str(e)}"
        )

@router.get("/", response_model=List[Product])
async def get_products(
    current_user = Depends(auth_service.get_current_active_user),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    filter_by: Optional[str] = Query(None, description="Filter type (all, favorites)"),
    sort_by: Optional[str] = Query("date", description="Sort field (date, price, name)")
):
    """Get all products for the current user."""
    try:
        db = get_database()
        query = {"user_id": str(current_user.id)}
        
        # Apply filters
        if is_active is not None:
            query["is_active"] = is_active
        if filter_by == "favorites":
            query["is_favorite"] = True
            
        # Get products
        cursor = db.products.find(query)
        
        # Apply sorting
        if sort_by == "price":
            cursor = cursor.sort("current_price", 1)
        elif sort_by == "name":
            cursor = cursor.sort("title", 1)
        else:  # default sort by date
            cursor = cursor.sort("created_at", -1)
            
        products = await cursor.to_list(length=None)
        return [Product(**p) for p in products]
    except Exception as e:
        logger.error(f"Error getting products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/favorites", response_model=List[Product])
async def get_favorites(
    current_user = Depends(auth_service.get_current_active_user)
):
    """Get favorite products for the current user."""
    try:
        return await product_service.get_products(str(current_user.id), filter_by="favorites")
    except Exception as e:
        logger.error(f"Error getting favorite products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{product_id}", response_model=Product)
async def get_product(
    product_id: str,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Get a specific product."""
    try:
        product = await product_service.get_product(product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        if str(product.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this product"
            )
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{product_id}", response_model=Product)
async def update_product(
    product_id: str,
    product_update: ProductUpdate,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Update a product."""
    try:
        existing_product = await product_service.get_product(product_id)
        if not existing_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        if str(existing_product.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this product"
            )
            
        updated_product = await product_service.update_product(product_id, product_update)
        if not updated_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return updated_product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Delete a product."""
    try:
        existing_product = await product_service.get_product(product_id)
        if not existing_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        if str(existing_product.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this product"
            )
            
        success = await product_service.delete_product(product_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{product_id}/favorite", response_model=Product)
async def toggle_favorite(
    product_id: str,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Toggle favorite status of a product."""
    try:
        existing_product = await product_service.get_product(product_id)
        if not existing_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        if str(existing_product.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this product"
            )
            
        updated_product = await product_service.toggle_favorite(product_id, str(current_user.id))
        if not updated_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return updated_product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{product_id}/favorite-status")
async def get_product_favorite_status(
    product_id: str,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Get favorite status of a product."""
    try:
        existing_product = await product_service.get_product(product_id)
        if not existing_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        if str(existing_product.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this product"
            )
            
        is_favorite = await product_service.get_product_favorite_status(product_id, str(current_user.id))
        return {"is_favorite": is_favorite}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting favorite status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{product_id}/history", response_model=List[PriceHistory])
async def get_price_history(
    product_id: str,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Get price history for a product."""
    try:
        existing_product = await product_service.get_product(product_id)
        if not existing_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        if str(existing_product.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this product"
            )
            
        return await product_service.get_price_history(product_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/extract-info/")
async def extract_info():
    """Placeholder for extract info endpoint."""
    return {"message": "Not implemented yet"}