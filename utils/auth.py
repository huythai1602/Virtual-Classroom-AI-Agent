"""
Authentication utilities
"""
from fastapi import HTTPException, Header
from jose import JWTError, jwt
from typing import Optional

from config.settings import settings
from fastapi.security import HTTPBearer

# Shared Security Scheme for Swagger UI
security = HTTPBearer(
    scheme_name="Bearer Token",
    description="Enter your JWT token (without 'Bearer' prefix)"
)


def verify_token(authorization: str) -> dict:
    """Verify JWT token and return payload"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def get_user_id(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from JWT token (Required authentication)"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        payload = verify_token(authorization)
        # Support multiple user_id field names, prioritizing 'uid' (BigInt mapped in DB)
        user_id = payload.get("uid") or payload.get("sub") or payload.get("user_id") or payload.get("userId")
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        return str(user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


def get_optional_user(authorization: Optional[str] = Header(None)) -> str:
    """Get user_id from token or return 'anonymous' (Optional auth for CORS)"""
    if not authorization:
        return "anonymous"
    
    try:
        return get_user_id(authorization)
    except HTTPException:
        return "anonymous"
