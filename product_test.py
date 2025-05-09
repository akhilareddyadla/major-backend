#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import sys

def main():
    # Login to get token
    username = "testuser99"
    password = "testpassword99"
    
    print(f"Logging in as {username}...")
    login_response = requests.post(
        "http://127.0.0.1:8000/api/v1/auth/login",
        data={
            "username": username,
            "password": password
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    
    print(f"Login Status: {login_response.status_code}")
    if login_response.status_code != 200:
        print("Login failed:", login_response.text)
        return
    
    try:
        # Get token from response
        token_data = login_response.json()
        token = token_data["access_token"]
        print(f"Token: {token[:20]}...")
        
        # Create headers with token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Check if we can get user info
        me_response = requests.get(
            "http://127.0.0.1:8000/api/v1/auth/me",
            headers=headers
        )
        
        print(f"Me Status: {me_response.status_code}")
        if me_response.status_code == 200:
            print("User info:", me_response.json())
            
            # Now try to create a product
            product_data = {
                "name": "Simple Test Product",
                "url": "https://example.com/simple-product",
                "website_type": "custom",
                "current_price": 9.99,
                "currency": "USD",
                "image_url": "https://example.com/simple-image.jpg",
                "description": "A very simple product for testing"
            }
            
            # Attempt to create product
            print("\nCreating product...")
            product_response = requests.post(
                "http://127.0.0.1:8000/api/v1/products/",
                json=product_data,
                headers=headers
            )
            
            print(f"Product Create Status: {product_response.status_code}")
            print("Response:", product_response.text)
            
            if product_response.status_code == 500:
                print("\nServer error occurred. This might be due to:")
                print("1. MongoDB connection issues")
                print("2. Scraping module errors")
                print("3. Other server-side issues")
                print("\nPlease check the server logs for more details.")
        else:
            print("Failed to get user info:", me_response.text)
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 