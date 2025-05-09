from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from typing import List, Dict
from ..services.price_analytics import PriceAnalyticsService
from ..services.chart_service import ChartService
from ..models.price_history import PriceHistory
from ..db.mongodb import get_database
from bson import ObjectId
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/price-analytics",
    tags=["price-analytics"]
)

@router.get("/{product_id}/enhanced-history")
async def get_enhanced_price_history(
    product_id: str, 
    chart_type: str = Query("line", regex="^(line|bar)$"),
    db=Depends(get_database)
):
    try:
        # Convert string ID to ObjectId
        product_obj_id = ObjectId(product_id)
        
        # Get price history from database
        price_history_collection = db["price_history"]
        price_history_data = await price_history_collection.find(
            {"product_id": product_obj_id}
        ).sort("timestamp", 1).to_list(length=None)
        
        if not price_history_data:
            # Return empty but valid structure
            return {
                "chart_data": ChartService.format_chart_data([], chart_type),
                "analytics": {
                    "price_change_percentage": 0.0,
                    "trend": "neutral",
                    "change_frequency": {"daily": 0, "weekly": 0, "monthly": 0}
                }
            }
        
        # Convert database records to PriceHistory objects
        price_history = []
        for ph in price_history_data:
            try:
                price_history.append(PriceHistory(
                    product_id=str(ph["product_id"]),
                    price=float(ph["price"]),
                    timestamp=ph["timestamp"],
                    currency=ph.get("currency", "INR"),
                    is_discount=ph.get("is_discount", False),
                    discount_percentage=ph.get("discount_percentage"),
                    source=ph.get("source", "manual")
                ))
            except Exception as e:
                logger.error(f"Error converting price history entry: {str(e)}")
                continue
        
        # Get analytics
        analytics = PriceAnalyticsService.get_enhanced_price_history(price_history)
        
        # Format chart data
        chart_data = ChartService.format_chart_data(price_history, chart_type)
        
        return {
            "chart_data": chart_data,
            "analytics": {
                "price_change_percentage": analytics.get("price_change_percentage", 0.0),
                "trend": analytics.get("trend", "neutral"),
                "change_frequency": analytics.get("change_frequency", {"daily": 0, "weekly": 0, "monthly": 0})
            }
        }
        
    except Exception as e:
        logger.error(f"Error in get_enhanced_price_history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}/export")
async def export_price_history(
    product_id: str,
    format: str = Query("csv", regex="^(csv|json|excel)$"),
    db=Depends(get_database)
):
    try:
        product_obj_id = ObjectId(product_id)
        
        # Get price history from database
        price_history_collection = db["price_history"]
        price_history_data = await price_history_collection.find(
            {"product_id": product_obj_id}
        ).sort("timestamp", 1).to_list(length=None)
        
        if not price_history_data:
            raise HTTPException(status_code=404, detail="No price history data available for export")
        
        # Convert to PriceHistory objects
        price_history = []
        for ph in price_history_data:
            try:
                price_history.append(PriceHistory(
                    product_id=str(ph["product_id"]),
                    price=float(ph["price"]),
                    timestamp=ph["timestamp"],
                    currency=ph.get("currency", "INR"),
                    is_discount=ph.get("is_discount", False),
                    discount_percentage=ph.get("discount_percentage"),
                    source=ph.get("source", "manual")
                ))
            except Exception as e:
                logger.error(f"Error converting price history entry: {str(e)}")
                continue
        
        try:
            filename, data, content_type = ChartService.export_data(price_history, format)
            
            return Response(
                content=data,
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(f"Error in export_price_history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 