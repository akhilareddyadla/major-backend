#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import subprocess
import sys

def run_curl(method, url, headers=None, data=None):
    """Run a curl command with the given parameters"""
    cmd = ["curl", "-s", "-X", method, url]
    
    if headers:
        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])
    
    if data:
        if isinstance(data, dict):
            # For JSON data
            cmd.extend(["-d", json.dumps(data)])
        else:
            # For form data
            cmd.extend(["-d", data])
    
    print(f"\nRunning: {' '.join(cmd)}")
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode != 0:
        print(f"Error: {process.stderr}")
        return None
    
    print(f"Response: {process.stdout}")
    
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError:
        print("Warning: Response is not valid JSON")
        return process.stdout

def main():
    base_url = "http://127.0.0.1:8000/api/v1"
    
    print("========= FASTAPI TEST SCRIPT =========")
    print("This script will test creating a user, logging in, and creating a product")
    
    # 1. Create a user
    username = "testuser99"
    password = "testpassword99"
    email = "test99@example.com"
    
    print("\n1. Creating a user...")
    user_data = {
        "username": username,
        "password": password,
        "email": email,
        "full_name": "Test User 99"
    }
    
    signup_response = run_curl("POST", f"{base_url}/auth/signup", 
                             headers={"Content-Type": "application/json"},
                             data=user_data)
    
    # 2. Login to get token
    print("\n2. Logging in...")
    form_data = f"username={username}&password={password}"
    
    login_response = run_curl("POST", f"{base_url}/auth/login",
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                            data=form_data)
    
    if not login_response or "access_token" not in login_response:
        print("Login failed. Exiting...")
        return
    
    token = login_response["access_token"]
    print(f"Token received: {token[:20]}...")
    
    # 3. Get current user info
    print("\n3. Getting user info...")
    user_info = run_curl("GET", f"{base_url}/auth/me",
                       headers={"Authorization": f"Bearer {token}"})
    
    # 4. Create a product
    print("\n4. Creating a product...")
    product_data = {
        "name": "Test Product",
        "url": "https://example.com/product",
        "website_type": "custom",
        "current_price": 99.99,
        "currency": "USD",
        "image_url": "https://example.com/product.jpg",
        "description": "This is a test product"
    }
    
    product_response = run_curl("POST", f"{base_url}/products/",
                              headers={
                                  "Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json"
                              },
                              data=product_data)
    
    if not product_response or "id" not in product_response:
        print("Failed to create product. Exiting...")
        return
    
    product_id = product_response["id"]
    
    # 5. Get the product
    print(f"\n5. Getting product with ID: {product_id}...")
    run_curl("GET", f"{base_url}/products/{product_id}",
           headers={"Authorization": f"Bearer {token}"})
    
    # 6. Get all products
    print("\n6. Getting all products...")
    run_curl("GET", f"{base_url}/products/",
           headers={"Authorization": f"Bearer {token}"})

if __name__ == "__main__":
    main() 