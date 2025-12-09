
import os
from jose import jwt, JWTError
from datetime import datetime, timedelta

# Mock settings based on what I saw in settings.py
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    print(f"Verifying token with key: {JWT_SECRET_KEY}")
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        print("Token is valid. Payload:", payload)
        return payload
    except JWTError as e:
        print(f"Token invalid: {e}")
        return None

if __name__ == "__main__":
    print("-" * 50)
    print("TEST 1: Create and Verify (Happy Path)")
    # 1. Create a token
    sample_data = {"sub": "user_123"}
    token = create_access_token(sample_data)
    print(f"Generated Token: {token}")
    
    # 2. Verify it
    verify_token(token)

    print("-" * 50)
    print("TEST 2: Verify with WRONG Key (Simulation)")
    # Simulate if client has token signed with 'secret_A' but server uses 'your-secret-key-change-in-production'
    wrong_key = "different_secret"
    wrong_token = jwt.encode(sample_data, wrong_key, algorithm=JWT_ALGORITHM)
    print(f"Token signed with '{wrong_key}': {wrong_token}")
    
    verify_token(wrong_token)
