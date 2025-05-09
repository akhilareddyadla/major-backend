import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    try:
        response = requests.get(f"{BASE_URL}/health")
        print("\nHealth Check:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to the server. Make sure it's running on port 8000")

def test_signup():
    test_user = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/signup",
            json=test_user,
            headers={"Content-Type": "application/json"}
        )
        print("\nSignup Test:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to the server. Make sure it's running on port 8000")

if __name__ == "__main__":
    print("Testing API endpoints...")
    test_health()
    test_signup() 