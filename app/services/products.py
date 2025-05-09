from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from app.db.mongodb import get_collection
from app.models.product import Product, ProductCreate, ProductUpdate, PriceHistory
import logging
from fastapi import HTTPException, status
import pymongo
import traceback
from enum import Enum

logger = logging.getLogger(__name__)

class WebsiteType(str, Enum):
    amazon = "amazon"
    flipkart = "flipkart"
    ebay = "ebay"
    other = "other"
    meesho = "meesho"

class ProductService:
    def __init__(self):
        self.products_collection = None

    async def initialize(self):
        """Initialize the products collection."""
        try:
            self.products_collection = get_collection("products")
            logger.info("ProductService initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ProductService: {str(e)}")
            print(traceback.format_exc())
            raise

    async def create_product(self, user_id: str, product: ProductCreate) -> Product:
        """Create a new product."""
        try:
            await self.initialize()
            product_dict = product.model_dump()
            product_dict["user_id"] = str(user_id)
            product_dict["created_at"] = datetime.utcnow()
            product_dict["updated_at"] = datetime.utcnow()
            product_dict["price_history"] = [{
                "price": product.current_price,
                "timestamp": datetime.utcnow(),
                "currency": product.currency,
                "is_discount": False
            }]

            result = await self.products_collection.insert_one(product_dict)
            product_dict["_id"] = result.inserted_id
            return Product(**product_dict)
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating product: {str(e)}"
            )

    async def get_products(self, user_id: str, is_active: Optional[bool] = None, filter_by: Optional[str] = None, sort_by: Optional[str] = "date") -> List[Product]:
        """Get products with filtering and sorting."""
        try:
            await self.initialize()
            query = {"user_id": str(user_id)}
            
            # Only add is_active to query if it's explicitly provided
            if is_active is not None:
                query["is_active"] = is_active
            
            if filter_by == "favorites":
                query["is_favorite"] = True

            sort_options = {
                "date": [("created_at", pymongo.DESCENDING)],
                "price": [("current_price", pymongo.ASCENDING)],
                "name": [("name", pymongo.ASCENDING)]
            }
            sort_order = sort_options.get(sort_by, sort_options["date"])

            cursor = self.products_collection.find(query).sort(sort_order)
            products = await cursor.to_list(length=None)
            
            # Return empty list if no products found
            if not products:
                return []
            
            # Convert MongoDB documents to Product models
            return [Product(**{**product, "_id": str(product["_id"])}) for product in products]

        except Exception as e:
            logger.error(f"Error in get_products: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    async def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID."""
        try:
            await self.initialize()
            try:
                object_id = ObjectId(product_id)
            except Exception as e:
                logger.error(f"Invalid ObjectId format: {product_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid product ID format: {product_id}"
                )
                
            product = await self.products_collection.find_one({"_id": object_id})
            return Product(**product) if product else None
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting product: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting product: {str(e)}"
            )

    async def update_product(self, product_id: str, product_update: ProductUpdate) -> Optional[Product]:
        """Update a product."""
        try:
            await self.initialize()
            try:
                object_id = ObjectId(product_id)
            except Exception as e:
                logger.error(f"Invalid ObjectId format: {product_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid product ID format: {product_id}"
                )
                
            update_data = product_update.model_dump(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()
            
            if "current_price" in update_data:
                price_history = {
                    "price": update_data["current_price"],
                    "timestamp": datetime.utcnow(),
                    "currency": update_data.get("currency", "INR"),
                    "is_discount": False
                }
                await self.products_collection.update_one(
                    {"_id": object_id},
                    {"$push": {"price_history": price_history}}
                )

            result = await self.products_collection.update_one(
                {"_id": object_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update product"
                )

            updated_product = await self.products_collection.find_one({"_id": object_id})
            if not updated_product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found after update"
                )

            return Product(**updated_product)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating product: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error updating product"
            )

    async def delete_product(self, product_id: str) -> bool:
        """Delete a product."""
        try:
            await self.initialize()
            try:
                object_id = ObjectId(product_id)
            except Exception as e:
                logger.error(f"Invalid ObjectId format: {product_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid product ID format: {product_id}"
                )
                
            result = await self.products_collection.delete_one({"_id": object_id})
            return result.deleted_count > 0
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting product"
            )

    async def toggle_favorite(self, product_id: str, user_id: str) -> Product:
        """Toggle favorite status of a product."""
        try:
            await self.initialize()
            try:
                object_id = ObjectId(product_id)
            except Exception as e:
                logger.error(f"Invalid ObjectId format: {product_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid product ID format: {product_id}"
                )
                
            product = await self.products_collection.find_one({"_id": object_id})
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found"
                )
                
            if str(product["user_id"]) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to modify this product"
                )
                
            is_favorite = not product.get("is_favorite", False)
            result = await self.products_collection.update_one(
                {"_id": object_id},
                {"$set": {"is_favorite": is_favorite}}
            )
            
            if result.modified_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update favorite status"
                )
                
            updated_product = await self.products_collection.find_one({"_id": object_id})
            return Product(**updated_product)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error toggling favorite: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error toggling favorite status"
            )

    async def get_product_favorite_status(self, product_id: str, user_id: str) -> bool:
        """Get favorite status of a product."""
        try:
            await self.initialize()
            try:
                object_id = ObjectId(product_id)
            except Exception as e:
                logger.error(f"Invalid ObjectId format: {product_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid product ID format: {product_id}"
                )
                
            product = await self.products_collection.find_one({"_id": object_id})
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found"
                )
                
            if str(product["user_id"]) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this product"
                )
                
            return bool(product.get("is_favorite", False))
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting favorite status: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error getting favorite status"
            )

# Create a single instance of ProductService
product_service = ProductService() 