from typing import List, Dict, Optional
from datetime import datetime
import csv
import io
import json
from ..models.price_history import PriceHistory

class ChartService:
    @staticmethod
    def format_chart_data(price_history: List[PriceHistory], chart_type: str = "line") -> Dict:
        """Format price history data for different chart types."""
        if not price_history:
            return {
                "labels": [],
                "datasets": [{
                    "data": [],
                    "type": chart_type
                }]
            }

        # Sort price history by timestamp
        sorted_history = sorted(price_history, key=lambda x: x.timestamp)

        # Format data based on chart type
        if chart_type == "bar":
            return {
                "labels": [ph.timestamp.strftime("%Y-%m-%d %H:%M") for ph in sorted_history],
                "datasets": [{
                    "label": "Price History",
                    "data": [float(ph.price) for ph in sorted_history],
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "borderColor": "rgba(75, 192, 192, 1)",
                    "borderWidth": 1,
                    "type": "bar"
                }]
            }
        else:  # line chart
            return {
                "labels": [ph.timestamp.strftime("%Y-%m-%d %H:%M") for ph in sorted_history],
                "datasets": [{
                    "label": "Price History",
                    "data": [float(ph.price) for ph in sorted_history],
                    "borderColor": "rgba(75, 192, 192, 1)",
                    "tension": 0.1,
                    "fill": False,
                    "type": "line"
                }]
            }

    @staticmethod
    def export_data(price_history: List[PriceHistory], format: str = "csv") -> tuple[str, bytes, str]:
        """Export price history data in different formats."""
        if not price_history:
            raise ValueError("No data to export")

        sorted_history = sorted(price_history, key=lambda x: x.timestamp)
        
        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(["Date", "Price", "Currency", "Is Discount", "Discount Percentage"])
            
            # Write data
            for ph in sorted_history:
                writer.writerow([
                    ph.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    float(ph.price),
                    ph.currency,
                    ph.is_discount,
                    ph.discount_percentage or ""
                ])
            
            return (
                "price_history.csv",
                output.getvalue().encode('utf-8'),
                "text/csv"
            )
            
        elif format.lower() == "json":
            data = {
                "price_history": [
                    {
                        "date": ph.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "price": float(ph.price),
                        "currency": ph.currency,
                        "is_discount": ph.is_discount,
                        "discount_percentage": ph.discount_percentage
                    }
                    for ph in sorted_history
                ],
                "export_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "total_records": len(sorted_history)
            }
            
            return (
                "price_history.json",
                json.dumps(data, indent=2).encode('utf-8'),
                "application/json"
            )
            
        elif format.lower() == "excel":
            try:
                import pandas as pd
                
                # Create DataFrame
                df = pd.DataFrame([
                    {
                        "Date": ph.timestamp,
                        "Price": float(ph.price),
                        "Currency": ph.currency,
                        "Is Discount": ph.is_discount,
                        "Discount Percentage": ph.discount_percentage
                    }
                    for ph in sorted_history
                ])
                
                # Create Excel file in memory
                output = io.BytesIO()
                df.to_excel(output, index=False, sheet_name="Price History")
                
                return (
                    "price_history.xlsx",
                    output.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except ImportError:
                raise ValueError("Excel export requires pandas to be installed")
        
        else:
            raise ValueError(f"Unsupported export format: {format}") 