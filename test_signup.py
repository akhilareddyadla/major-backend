#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import sys

def main():
    # Check if username, password, and email were provided
    if len(sys.argv) != 4:
        print("Usage: python test_signup.py <username> <password> <email>")
        print("Example: python test_signup.py testuser testpassword test@example.com")
        sys.exit(1)
        
    username = sys.argv[1]
    password = sys.argv[2]
    email = sys.argv[3]
    
    # Create user data
    user_data = {
        "username": username,
        "password": password,
        "email": email,
        "full_name": f"{username.capitalize()} User"
    }
    
    print(f"Creating user {username}...")
    
    # Send signup request
    signup_response = requests.post(
        "http://127.0.0.1:8000/api/v1/auth/signup",
        json=user_data
    )
    
    print(f"Signup Status Code: {signup_response.status_code}")
    
    if signup_response.status_code == 200:
        print("User created successfully!")
        print("User data:", signup_response.json())
        
        # Now login to get a token
        print(f"\nLogging in as {username}...")
        
        login_data = {
            "username": username,
            "password": password
        }
        
        login_response = requests.post(
            "http://127.0.0.1:8000/api/v1/auth/login",
            data=login_data
        )
        
        print(f"Login Status Code: {login_response.status_code}")
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            print("Successfully logged in and got token!")
            
            # Save token to file
            with open('token.txt', 'w') as f:
                f.write(token)
                
            print("Token saved to token.txt")
            print("\nNow you can create products with this token.")
            print("Run: python test_create_product.py", username, password)
        else:
            print("Login failed!")
            print("Response:", login_response.text)
    else:
        print("User creation failed!")
        print("Response:", signup_response.text)
        
if __name__ == "__main__":
    main() 