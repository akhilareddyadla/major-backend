#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import sys

# Complete Product data (all fields provided to avoid scraping)
product_data = {
    "name": "Test Product",
    "url": "https://example.com/product",
    "website_type": "custom",  # Use "custom" type which might have simpler scraping
    "current_price": 99.99,
    "currency": "USD",
    "image_url": "https://example.com/product.jpg",
    "description": "This is a test product with complete data to avoid server-side scraping"
}

def main():
    # Check if username and password were provided
    if len(sys.argv) != 3:
        print("Usage: python test_create_product.py <username> <password>")
        print("Example: python test_create_product.py testuser testpassword")
        sys.exit(1)
        
    username = sys.argv[1]
    password = sys.argv[2]
    
    print(f"Logging in as {username}...")
    
    # Try to login
    login_data = {
        "username": username,
        "password": password
    }
    
    login_response = requests.post(
        "http://127.0.0.1:8000/api/v1/auth/login",
        data=login_data
    )
    
    if login_response.status_code != 200:
        print("Login failed!")
        print("Response:", login_response.text)
        sys.exit(1)
        
    token = login_response.json().get("access_token")
    print("Successfully logged in and got token!")
    
    # Save token to file
    with open('token.txt', 'w') as f:
        f.write(token)
        
    # Now create a product
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("\nCreating product...")
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/products/",
        headers=headers,
        json=product_data
    )
    
    print(f"Create Product Status Code: {response.status_code}")
    
    if response.status_code == 200 or response.status_code == 201:
        print("Product created successfully!")
        print("Product data:", response.json())
        
        # Get the product ID
        product_id = response.json().get("id")
        
        # Now test getting the product
        print(f"\nRetrieving product with ID: {product_id}")
        get_response = requests.get(
            f"http://127.0.0.1:8000/api/v1/products/{product_id}",
            headers=headers
        )
        
        print(f"Get Product Status Code: {get_response.status_code}")
        
        if get_response.status_code == 200:
            print("Product retrieved successfully!")
            print("Product data:", get_response.json())
        else:
            print("Failed to retrieve product.")
            print("Response:", get_response.text)
    else:
        print("Failed to create product.")
        print("Response:", response.text)
        
if __name__ == "__main__":
    main() 