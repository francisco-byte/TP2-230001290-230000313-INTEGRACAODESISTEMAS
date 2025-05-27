import jwt
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class OAuth2JWTAuthenticator:
    def __init__(self, secret_key: str, issuer: str = "produtos-api"):
        self.secret_key = secret_key
        self.issuer = issuer
        self.audience = "produtos-client"
        
    def generate_access_token(self, user_id: str, email: str, roles: List[str], permissions: List[str]) -> str:
        """Generate OAuth2 JWT access token (RFC 7519)"""
        payload = {
            'user_id': user_id,
            'email': email,
            'roles': roles,
            'permissions': permissions,
            'scope': ' '.join(permissions),  # OAuth2 scopes
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow(),
            'iss': self.issuer,  # Issuer
            'aud': self.audience,  # Audience
            'token_type': 'access_token',
            'jti': f"{user_id}_{int(datetime.utcnow().timestamp())}"  # JWT ID
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def generate_refresh_token(self, user_id: str) -> str:
        """Generate OAuth2 refresh token (RFC 6749)"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(days=30),  # 30 days
            'iat': datetime.utcnow(),
            'iss': self.issuer,
            'aud': self.audience,
            'token_type': 'refresh_token',
            'jti': f"refresh_{user_id}_{int(datetime.utcnow().timestamp())}"
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_access_token(self, token: str) -> Optional[Dict]:
        """Verify OAuth2 JWT access token"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=['HS256'],
                audience=self.audience,
                issuer=self.issuer
            )
            
            # Ensure it's an access token
            if payload.get('token_type') != 'access_token':
                return None
                
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except jwt.InvalidAudienceError:
            return None
        except jwt.InvalidIssuerError:
            return None
    
    def verify_refresh_token(self, token: str) -> Optional[Dict]:
        """Verify OAuth2 refresh token"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=['HS256'],
                audience=self.audience,
                issuer=self.issuer
            )
            
            # Ensure it's a refresh token
            if payload.get('token_type') != 'refresh_token':
                return None
                
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except jwt.InvalidAudienceError:
            return None
        except jwt.InvalidIssuerError:
            return None
    
    def check_scope_permission(self, payload: Dict, required_scope: str) -> bool:
        """Check if JWT token has required OAuth2 scope"""
        token_permissions = payload.get('permissions', [])
        return required_scope in token_permissions

class OAuth2Provider:
    """OAuth2 Authorization Server implementation (RFC 6749)"""
    
    def __init__(self):
        # Mock OAuth2 user database
        # In production, this would integrate with external OAuth providers
        # like Google, Microsoft, GitHub, Auth0, etc.
        self.users_db = {
            "admin": {
                "password": "admin123",
                "user_id": "admin_001",
                "email": "admin@produtos.com",
                "roles": ["admin", "user"],
                "active": True,
                "client_id": "produtos_admin_client"
            },
            "user": {
                "password": "user123",
                "user_id": "user_001", 
                "email": "user@produtos.com",
                "roles": ["user"],
                "active": True,
                "client_id": "produtos_user_client"
            },
            "readonly": {
                "password": "readonly123",
                "user_id": "readonly_001",
                "email": "readonly@produtos.com", 
                "roles": ["readonly"],
                "active": True,
                "client_id": "produtos_readonly_client"
            }
        }
        
        # OAuth2 scopes mapping (RFC 6749 Section 3.3)
        self.role_scopes = {
            "admin": [
                "create_product",    # Can create products
                "read_product",      # Can read products
                "update_product",    # Can update products
                "delete_product",    # Can delete products
                "admin_access"       # Administrative access
            ],
            "user": [
                "create_product",    # Can create products
                "read_product",      # Can read products
                "update_product"     # Can update products
            ],
            "readonly": [
                "read_product"       # Can only read products
            ]
        }
    
    async def authenticate_user_password_grant(self, username: str, password: str, requested_scope: str = None) -> Optional[Dict]:
        """OAuth2 Resource Owner Password Credentials Grant (RFC 6749 Section 4.3)"""
        user = self.users_db.get(username)
        
        if user and user["password"] == password and user["active"]:
            # Get user permissions based on roles
            permissions = await self.get_user_permissions(user["roles"])
            
            # Filter permissions based on requested scope
            if requested_scope:
                requested_permissions = requested_scope.split()
                # Only grant permissions that user has AND requested
                granted_permissions = [p for p in requested_permissions if p in permissions]
            else:
                granted_permissions = permissions
            
            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "roles": user["roles"],
                "permissions": granted_permissions,
                "client_id": user["client_id"]
            }
        return None
    
    async def refresh_token_grant(self, refresh_token: str, jwt_auth: OAuth2JWTAuthenticator) -> Optional[Dict]:
        """OAuth2 Refresh Token Grant (RFC 6749 Section 6)"""
        payload = jwt_auth.verify_refresh_token(refresh_token)
        if not payload:
            return None
            
        user_id = payload.get('user_id')
        
        # Find user by ID
        user = None
        for username, user_data in self.users_db.items():
            if user_data["user_id"] == user_id and user_data["active"]:
                user = user_data
                break
        
        if user:
            permissions = await self.get_user_permissions(user["roles"])
            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "roles": user["roles"],
                "permissions": permissions,
                "client_id": user["client_id"]
            }
        return None
    
    async def get_user_permissions(self, roles: List[str]) -> List[str]:
        """Convert user roles to OAuth2 scopes/permissions"""
        permissions = set()
        for role in roles:
            permissions.update(self.role_scopes.get(role, []))
        return list(permissions)
    
    async def validate_client(self, client_id: str) -> bool:
        """Validate OAuth2 client (RFC 6749 Section 2)"""
        # In production, this would check registered OAuth2 clients
        valid_clients = [
            "produtos_admin_client",
            "produtos_user_client", 
            "produtos_readonly_client",
            "produtos_web_client",
            "produtos_mobile_client"
        ]
        return client_id in valid_clients
    
    async def generate_authorization_code(self, user_id: str, client_id: str, scope: str) -> str:
        """Generate OAuth2 authorization code for Authorization Code Grant (RFC 6749 Section 4.1)"""
        # This would be used for web-based OAuth2 flows
        code_payload = {
            'user_id': user_id,
            'client_id': client_id,
            'scope': scope,
            'exp': datetime.utcnow() + timedelta(minutes=10),  # Short-lived
            'iat': datetime.utcnow(),
            'code_type': 'authorization_code'
        }
        return jwt.encode(code_payload, "auth_code_secret", algorithm='HS256')

# OAuth2 error responses (RFC 6749 Section 5.2)
class OAuth2Error:
    INVALID_REQUEST = "invalid_request"
    INVALID_CLIENT = "invalid_client" 
    INVALID_GRANT = "invalid_grant"
    UNAUTHORIZED_CLIENT = "unauthorized_client"
    UNSUPPORTED_GRANT_TYPE = "unsupported_grant_type"
    INVALID_SCOPE = "invalid_scope"
    ACCESS_DENIED = "access_denied"
    UNSUPPORTED_RESPONSE_TYPE = "unsupported_response_type"
    SERVER_ERROR = "server_error"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"

# Legacy compatibility functions (for existing code)
async def authenticate_user(credentials: dict) -> Optional[str]:
    """Legacy function - use OAuth2Provider.authenticate_user_password_grant instead"""
    oauth2_provider = OAuth2Provider()
    username = credentials.get('username')
    password = credentials.get('password')
    
    user_data = await oauth2_provider.authenticate_user_password_grant(username, password)
    if user_data:
        return user_data['user_id']
    return None

async def get_user_permissions(user_id: str) -> list:
    """Legacy function - use OAuth2Provider.get_user_permissions instead"""
    # Map user IDs to roles for backward compatibility
    user_role_map = {
        "admin_001": ["admin", "user"],
        "user_001": ["user"], 
        "readonly_001": ["readonly"],
        # Legacy IDs
        "admin_user": ["admin", "user"],
        "regular_user": ["user"],
        "readonly_user": ["readonly"]
    }
    
    oauth2_provider = OAuth2Provider()
    roles = user_role_map.get(user_id, [])
    return await oauth2_provider.get_user_permissions(roles)

# WebSocketAuthenticator class for backward compatibility
class WebSocketAuthenticator(OAuth2JWTAuthenticator):
    """Legacy class - use OAuth2JWTAuthenticator instead"""
    
    def __init__(self, secret_key: str):
        super().__init__(secret_key)
    
    def generate_jwt_token(self, user_id: str, permissions: list) -> str:
        """Legacy method - use generate_access_token instead"""
        return self.generate_access_token(
            user_id=user_id,
            email=f"{user_id}@produtos.com",
            roles=["user"],
            permissions=permissions
        )
    
    def verify_jwt_token(self, token: str) -> Optional[dict]:
        """Legacy method - use verify_access_token instead"""
        return self.verify_access_token(token)
    
    def check_permission(self, payload: dict, required_permission: str) -> bool:
        """Legacy method - use check_scope_permission instead"""
        return self.check_scope_permission(payload, required_permission)