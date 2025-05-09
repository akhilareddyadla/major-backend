from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app.models.product import Product, ProductCreate, ProductUpdate, PriceHistory
from app.services.products import product_service
from app.services.auth import auth_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["products"])

def parse_bool(value: Optional[str] = Query(None, description="Filter by active status (true/false)")) -> Optional[bool]:
    if value is None:
        return None
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise ValueError("Invalid boolean value for is_active")

@router.post("/", response_model=Product)
async def create_product(
    product: ProductCreate,
    current_user = Depends(auth_service.get_current_active_user)
):
    """Create a new product."""
    try:
        return await product_service.create_product(str(current_user.id), product)
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/", response_model=List[Product])
async def get_products(
    current_user = Depends(auth_service.get_current_active_user),
    is_active: Optional[str] = Query(None, description="Filter by active status (true/false)"),
    filter_by: Optional[str] = Query(None, description="Filter type (all, favorites)"),
    sort_by: Optional[str] = Query("date", description="Sort field (date, price, name)")
):
    """Get all products for the current user."""
    try:
        is_active_bool = None
        if is_active is not None and is_active != "":
            is_active_bool = is_active.lower() in ("true", "1", "yes")
        products = await product_service.get_products(str(current_user.id), is_active_bool, filter_by, sort_by)
        return products if products else []
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
        # First get the product to check ownership
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
        # First get the product to check ownership
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
        # First get the product to check ownership
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
        # First get the product to check ownership
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
        # First get the product to check ownership
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