import jwt
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

class WebSocketAuthenticator:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        
    def generate_jwt_token(self, user_id: str, permissions: list) -> str:
        """Generate JWT token for authenticated user"""
        payload = {
            'user_id': user_id,
            'permissions': permissions,
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_jwt_token(self, token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def check_permission(self, payload: dict, required_permission: str) -> bool:
        """Check if user has required permission"""
        return required_permission in payload.get('permissions', [])

# OAuth2-like authentication flow
async def authenticate_user(credentials: dict) -> Optional[str]:
    """Simulate OAuth2 authentication"""
    username = credentials.get('username')
    password = credentials.get('password')
    
    # Mock authentication - replace with real OAuth2 flow
    user_db = {
        "admin": {"password": "admin123", "user_id": "admin_user"},
        "user": {"password": "user123", "user_id": "regular_user"},
        "readonly": {"password": "readonly123", "user_id": "readonly_user"}
    }
    
    user_data = user_db.get(username)
    if user_data and user_data["password"] == password:
        return user_data["user_id"]
    return None

async def get_user_permissions(user_id: str) -> list:
    """Get user permissions from database/OAuth2 provider"""
    permission_map = {
        "admin_user": ["create_product", "read_product", "update_product", "delete_product"],
        "regular_user": ["create_product", "read_product", "update_product"],
        "readonly_user": ["read_product"]
    }
    return permission_map.get(user_id, [])