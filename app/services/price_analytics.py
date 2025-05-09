from datetime import datetime, timedelta
from typing import List, Dict, Optional
from ..models.price_history import PriceHistory

class PriceAnalyticsService:
    @staticmethod
    def calculate_price_change_percentage(price_history: List[PriceHistory]) -> float:
        if len(price_history) < 2:
            return 0.0
        
        initial_price = price_history[0].price
        current_price = price_history[-1].price
        
        return ((current_price - initial_price) / initial_price) * 100

    @staticmethod
    def get_trend_indicator(price_history: List[PriceHistory], window: int = 5) -> str:
        if len(price_history) < window:
            return "neutral"
        
        recent_prices = [ph.price for ph in price_history[-window:]]
        avg_change = sum(b - a for a, b in zip(recent_prices[:-1], recent_prices[1:])) / (window - 1)
        
        if avg_change > 0:
            return "up"
        elif avg_change < 0:
            return "down"
        return "neutral"

    @staticmethod
    def calculate_price_change_frequency(price_history: List[PriceHistory]) -> Dict:
        if len(price_history) < 2:
            return {"daily": 0, "weekly": 0, "monthly": 0}
        
        changes = {
            "daily": 0,
            "weekly": 0,
            "monthly": 0
        }
        
        # Sort price history by timestamp
        sorted_history = sorted(price_history, key=lambda x: x.timestamp)
        
        # Calculate daily changes
        prev_day = None
        prev_price = None
        for ph in sorted_history:
            current_day = ph.timestamp.date()
            if prev_day and current_day != prev_day and ph.price != prev_price:
                changes["daily"] += 1
            prev_day = current_day
            prev_price = ph.price
        
        # Calculate weekly changes
        week_prices = {}
        for ph in sorted_history:
            week_num = ph.timestamp.isocalendar()[1]
            if week_num not in week_prices:
                week_prices[week_num] = []
            week_prices[week_num].append(ph.price)
        
        changes["weekly"] = sum(1 for prices in week_prices.values() 
                              if max(prices) != min(prices))
        
        # Calculate monthly changes
        month_prices = {}
        for ph in sorted_history:
            month = ph.timestamp.month
            if month not in month_prices:
                month_prices[month] = []
            month_prices[month].append(ph.price)
        
        changes["monthly"] = sum(1 for prices in month_prices.values() 
                               if max(prices) != min(prices))
        
        return changes

    @staticmethod
    def get_enhanced_price_history(price_history: List[PriceHistory]) -> Dict:
        if not price_history:
            return {}
        
        sorted_history = sorted(price_history, key=lambda x: x.timestamp)
        
        return {
            "price_change_percentage": PriceAnalyticsService.calculate_price_change_percentage(sorted_history),
            "trend": PriceAnalyticsService.get_trend_indicator(sorted_history),
            "change_frequency": PriceAnalyticsService.calculate_price_change_frequency(sorted_history),
            "price_points": [
                {
                    "price": ph.price,
                    "timestamp": ph.timestamp.isoformat(),
                    "currency": ph.currency,
                    "is_discount": ph.is_discount,
                    "discount_percentage": ph.discount_percentage
                }
                for ph in sorted_history
            ]
        } 