import jwt
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class OAuth2JWTAuthenticator:
    """Autenticador OAuth2 + JWT para gestão de tokens de acesso e renovação"""
    
    def __init__(self, secret_key: str, issuer: str = "produtos-api"):
        self.secret_key = secret_key  # Chave secreta para assinatura JWT
        self.issuer = issuer  # Emissor dos tokens
        self.audience = "produtos-client"  # Audiência dos tokens
        
    def generate_access_token(self, user_id: str, email: str, roles: List[str], permissions: List[str]) -> str:
        """Gera token de acesso OAuth2 JWT conforme RFC 7519"""
        payload = {
            'user_id': user_id,
            'email': email,
            'roles': roles,
            'permissions': permissions,
            'scope': ' '.join(permissions),  # Âmbitos OAuth2
            'exp': datetime.utcnow() + timedelta(hours=24),  # Expira em 24 horas
            'iat': datetime.utcnow(),  # Data de emissão
            'iss': self.issuer,  # Emissor
            'aud': self.audience,  # Audiência
            'token_type': 'access_token',
            'jti': f"{user_id}_{int(datetime.utcnow().timestamp())}"  # ID único do JWT
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def generate_refresh_token(self, user_id: str) -> str:
        """Gera token de renovação OAuth2 conforme RFC 6749"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(days=30),  # Expira em 30 dias
            'iat': datetime.utcnow(),
            'iss': self.issuer,
            'aud': self.audience,
            'token_type': 'refresh_token',
            'jti': f"refresh_{user_id}_{int(datetime.utcnow().timestamp())}"
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_access_token(self, token: str) -> Optional[Dict]:
        """Verifica e valida token de acesso OAuth2 JWT"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=['HS256'],
                audience=self.audience,
                issuer=self.issuer
            )
            
            # Garante que é um token de acesso
            if payload.get('token_type') != 'access_token':
                return None
                
            return payload
        except jwt.ExpiredSignatureError:
            # Token expirado
            return None
        except jwt.InvalidTokenError:
            # Token inválido
            return None
        except jwt.InvalidAudienceError:
            # Audiência incorrecta
            return None
        except jwt.InvalidIssuerError:
            # Emissor incorrecto
            return None
    
    def verify_refresh_token(self, token: str) -> Optional[Dict]:
        """Verifica e valida token de renovação OAuth2"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=['HS256'],
                audience=self.audience,
                issuer=self.issuer
            )
            
            # Garante que é um token de renovação
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
        """Verifica se o token JWT possui o âmbito OAuth2 necessário"""
        token_permissions = payload.get('permissions', [])
        return required_scope in token_permissions

class OAuth2Provider:
    """Implementação de Servidor de Autorização OAuth2 conforme RFC 6749"""
    
    def __init__(self):
        # Base de dados simulada de utilizadores OAuth2
        # Em produção, integraria com fornecedores OAuth externos
        # como Google, Microsoft, GitHub, Auth0, etc.
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
        
        # Mapeamento de âmbitos OAuth2 conforme RFC 6749 Secção 3.3
        self.role_scopes = {
            "admin": [
                "create_product",    # Pode criar produtos
                "read_product",      # Pode ler produtos
                "update_product",    # Pode actualizar produtos
                "delete_product",    # Pode eliminar produtos
                "admin_access"       # Acesso administrativo
            ],
            "user": [
                "create_product",    # Pode criar produtos
                "read_product",      # Pode ler produtos
                "update_product"     # Pode actualizar produtos
            ],
            "readonly": [
                "read_product"       # Pode apenas ler produtos
            ]
        }
    
    async def authenticate_user_password_grant(self, username: str, password: str, requested_scope: str = None) -> Optional[Dict]:
        """Fluxo OAuth2 Resource Owner Password Credentials Grant conforme RFC 6749 Secção 4.3"""
        user = self.users_db.get(username)
        
        if user and user["password"] == password and user["active"]:
            # Obtém permissões do utilizador baseadas nos papéis
            permissions = await self.get_user_permissions(user["roles"])
            
            # Filtra permissões baseadas no âmbito solicitado
            if requested_scope:
                requested_permissions = requested_scope.split()
                # Apenas concede permissões que o utilizador tem E solicitou
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
        """Fluxo OAuth2 Refresh Token Grant conforme RFC 6749 Secção 6"""
        payload = jwt_auth.verify_refresh_token(refresh_token)
        if not payload:
            return None
            
        user_id = payload.get('user_id')
        
        # Procura utilizador pelo ID
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
        """Converte papéis de utilizador em âmbitos/permissões OAuth2"""
        permissions = set()
        for role in roles:
            permissions.update(self.role_scopes.get(role, []))
        return list(permissions)
    
    async def validate_client(self, client_id: str) -> bool:
        """Valida cliente OAuth2 conforme RFC 6749 Secção 2"""
        # Em produção, verificaria clientes OAuth2 registados
        valid_clients = [
            "produtos_admin_client",
            "produtos_user_client", 
            "produtos_readonly_client",
            "produtos_web_client",
            "produtos_mobile_client"
        ]
        return client_id in valid_clients
    
    async def generate_authorization_code(self, user_id: str, client_id: str, scope: str) -> str:
        """Gera código de autorização OAuth2 para Authorization Code Grant conforme RFC 6749 Secção 4.1"""
        # Seria usado para fluxos OAuth2 baseados na web
        code_payload = {
            'user_id': user_id,
            'client_id': client_id,
            'scope': scope,
            'exp': datetime.utcnow() + timedelta(minutes=10),  # Vida curta
            'iat': datetime.utcnow(),
            'code_type': 'authorization_code'
        }
        return jwt.encode(code_payload, "auth_code_secret", algorithm='HS256')

# Respostas de erro OAuth2 conforme RFC 6749 Secção 5.2
class OAuth2Error:
    """Constantes para códigos de erro OAuth2 padronizados"""
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

# Funções de compatibilidade legada (para código existente)
async def authenticate_user(credentials: dict) -> Optional[str]:
    """Função legada - usar OAuth2Provider.authenticate_user_password_grant"""
    oauth2_provider = OAuth2Provider()
    username = credentials.get('username')
    password = credentials.get('password')
    
    user_data = await oauth2_provider.authenticate_user_password_grant(username, password)
    if user_data:
        return user_data['user_id']
    return None

async def get_user_permissions(user_id: str) -> list:
    """Função legada - usar OAuth2Provider.get_user_permissions"""
    # Mapeia IDs de utilizador para papéis para compatibilidade
    user_role_map = {
        "admin_001": ["admin", "user"],
        "user_001": ["user"], 
        "readonly_001": ["readonly"],
        # IDs legados
        "admin_user": ["admin", "user"],
        "regular_user": ["user"],
        "readonly_user": ["readonly"]
    }
    
    oauth2_provider = OAuth2Provider()
    roles = user_role_map.get(user_id, [])
    return await oauth2_provider.get_user_permissions(roles)

# Classe WebSocketAuthenticator para compatibilidade
class WebSocketAuthenticator(OAuth2JWTAuthenticator):
    """Classe legada - usar OAuth2JWTAuthenticator"""
    
    def __init__(self, secret_key: str):
        super().__init__(secret_key)
    
    def generate_jwt_token(self, user_id: str, permissions: list) -> str:
        """Método legado - usar generate_access_token"""
        return self.generate_access_token(
            user_id=user_id,
            email=f"{user_id}@produtos.com",
            roles=["user"],
            permissions=permissions
        )
    
    def verify_jwt_token(self, token: str) -> Optional[dict]:
        """Método legado - usar verify_access_token"""
        return self.verify_access_token(token)
    
    def check_permission(self, payload: dict, required_permission: str) -> bool:
        """Método legado - usar check_scope_permission"""
        return self.check_scope_permission(payload, required_permission)