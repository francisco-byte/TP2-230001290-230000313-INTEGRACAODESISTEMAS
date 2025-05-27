import asyncio
import websockets
import json
import pika
import threading
import logging
import time
import requests
from websocket_auth import OAuth2JWTAuthenticator, OAuth2Provider

# Configuração de logging para monitorização do sistema
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração OAuth2 + JWT para autenticação e autorização
jwt_auth = OAuth2JWTAuthenticator("your-super-secret-jwt-key-change-in-production")
oauth2_provider = OAuth2Provider()
connected_clients = {}  # Dicionário para gerir clientes conectados

async def notify_clients(message):
    """Notifica todos os clientes autenticados sobre actualizações do sistema"""
    if connected_clients:
        message_data = json.dumps(message)
        # Apenas notifica clientes autenticados por segurança
        authenticated_clients = [ws for ws, info in connected_clients.items() 
                               if info.get('authenticated', False)]
        if authenticated_clients:
            await asyncio.gather(
                *[client.send(message_data) for client in authenticated_clients],
                return_exceptions=True
            )

async def register(websocket):
    """Regista novo cliente WebSocket e envia informações de autenticação"""
    connected_clients[websocket] = {'authenticated': False}
    logger.info(f"Client connected: {websocket.remote_address}")
    await websocket.send(json.dumps({
        "status": "connected",
        "message": "OAuth2 authentication required",
        "auth_endpoint": "/auth",
        "supported_grant_types": ["password", "refresh_token"]
    }))

async def unregister(websocket):
    """Remove cliente da lista de conectados ao desconectar"""
    if websocket in connected_clients:
        client_info = connected_clients[websocket]
        if client_info.get('authenticated'):
            logger.info(f"OAuth2 user {client_info.get('user_id')} disconnected")
        del connected_clients[websocket]
    logger.info(f"Client disconnected: {websocket.remote_address}")

async def handle_oauth2_token_request(websocket, data):
    """Processa pedidos de token OAuth2 conforme RFC 6749"""
    try:
        grant_type = data.get('grant_type')
        
        if grant_type == 'password':
            # Fluxo OAuth2 Resource Owner Password Credentials Grant
            username = data.get('username')
            password = data.get('password')
            scope = data.get('scope', 'read_product')  # Âmbito OAuth2
            
            if not username or not password:
                await websocket.send(json.dumps({
                    "error": "invalid_request",
                    "error_description": "Missing username or password"
                }))
                return
            
            # Autentica utilizador e obtém permissões
            user_data = await oauth2_provider.authenticate_user_password_grant(username, password, scope)
            if user_data:
                # Gera tokens OAuth2 JWT
                access_token = jwt_auth.generate_access_token(
                    user_data['user_id'],
                    user_data['email'], 
                    user_data['roles'],
                    user_data['permissions']
                )
                refresh_token = jwt_auth.generate_refresh_token(user_data['user_id'])
                
                # Armazena informações do cliente autenticado
                connected_clients[websocket] = {
                    'authenticated': True,
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'roles': user_data['roles'],
                    'permissions': user_data['permissions'],
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }
                
                # Resposta de token OAuth2 conforme RFC 6749
                await websocket.send(json.dumps({
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 86400,  # 24 horas
                    "refresh_token": refresh_token,
                    "scope": ' '.join(user_data['permissions']),
                    "user_id": user_data['user_id'],
                    "email": user_data['email']
                }))
                
                logger.info(f"OAuth2 token issued for user {user_data['user_id']}")
                return
            else:
                await websocket.send(json.dumps({
                    "error": "invalid_grant",
                    "error_description": "Invalid username or password"
                }))
                return
                
        elif grant_type == 'refresh_token':
            # Fluxo OAuth2 Refresh Token Grant para renovação de tokens
            refresh_token = data.get('refresh_token')
            
            if not refresh_token:
                await websocket.send(json.dumps({
                    "error": "invalid_request", 
                    "error_description": "Missing refresh_token"
                }))
                return
            
            # Valida refresh token e gera novo access token
            user_data = await oauth2_provider.refresh_token_grant(refresh_token, jwt_auth)
            if user_data:
                new_access_token = jwt_auth.generate_access_token(
                    user_data['user_id'],
                    user_data['email'],
                    user_data['roles'], 
                    user_data['permissions']
                )
                
                # Actualiza token do cliente
                if websocket in connected_clients:
                    connected_clients[websocket]['access_token'] = new_access_token
                
                await websocket.send(json.dumps({
                    "access_token": new_access_token,
                    "token_type": "Bearer",
                    "expires_in": 86400,
                    "scope": ' '.join(user_data['permissions'])
                }))
                return
            else:
                await websocket.send(json.dumps({
                    "error": "invalid_grant",
                    "error_description": "Invalid refresh token"
                }))
                return
        else:
            await websocket.send(json.dumps({
                "error": "unsupported_grant_type",
                "error_description": f"Grant type '{grant_type}' not supported"
            }))
            return
            
    except Exception as e:
        logger.error(f"OAuth2 token request error: {str(e)}")
        await websocket.send(json.dumps({
            "error": "server_error",
            "error_description": "Internal server error"
        }))

async def verify_bearer_token(websocket, required_scope):
    """Verifica token Bearer OAuth2 e âmbito de permissões"""
    client_info = connected_clients.get(websocket)
    if not client_info or not client_info.get('authenticated'):
        return False, "access_denied", "Authentication required"
    
    # Verifica token JWT de acesso
    access_token = client_info.get('access_token')
    if access_token:
        payload = jwt_auth.verify_access_token(access_token)
        if not payload:
            return False, "invalid_token", "Access token expired or invalid"
        
        # Verifica âmbito OAuth2
        if jwt_auth.check_scope_permission(payload, required_scope):
            return True, None, None
        else:
            return False, "insufficient_scope", f"Required scope: {required_scope}"
    
    return False, "invalid_token", "No access token provided"

async def handle_api_request(websocket, action, data):
    """Processa pedidos API com autorização OAuth2"""
    try:
        # Mapeamento de acções para âmbitos OAuth2
        scope_mapping = {
            "create_rest": "create_product",
            "list_soap": "read_product",
            "update_grpc": "update_product", 
            "delete_graphql": "delete_product"
        }
        
        required_scope = scope_mapping.get(action)
        if not required_scope:
            await websocket.send(json.dumps({
                "error": "invalid_request",
                "error_description": f"Unknown action: {action}"
            }))
            return
        
        # Verifica autorização OAuth2
        authorized, error_code, error_description = await verify_bearer_token(websocket, required_scope)
        if not authorized:
            await websocket.send(json.dumps({
                "error": error_code,
                "error_description": error_description,
                "required_scope": required_scope
            }))
            return

        # Obtém contexto do utilizador
        client_info = connected_clients.get(websocket, {})
        user_id = client_info.get('user_id', 'unknown_user')

        # Executa chamadas API conforme a acção solicitada
        if action == "create_rest":
            # REST API - adiciona user_id directamente aos dados
            data['user_id'] = user_id
            response = requests.post("http://rest:8001/create", json=data, timeout=10)
            result = {"action": "create_rest", "success": True, "data": response.json()}
        
        elif action == "list_soap":
            try:
                # SOAP API - utiliza cliente Zeep para comunicação
                from zeep import Client as SoapClient
                client = SoapClient("http://soap:8002/?wsdl")
                produtos = client.service.read_all()
                result = {
                    "action": "list_soap", 
                    "success": True, 
                    "data": json.loads(produtos),
                    "requested_by": user_id
                }
            except Exception as soap_error:
                result = {"action": "list_soap", "success": False, "error": f"SOAP error: {str(soap_error)}"}
        
        elif action == "update_grpc":
            try:
                # gRPC API - filtra dados para o formato esperado pelo Produto message
                import grpc
                import produtos_pb2
                import produtos_pb2_grpc
                
                grpc_data = {
                    "id": data.get("id"),
                    "name": data.get("name"), 
                    "price": data.get("price"),
                    "stock": data.get("stock")
                }
                
                # Remove valores None para conformidade gRPC
                grpc_data = {k: v for k, v in grpc_data.items() if v is not None}
                
                channel = grpc.insecure_channel('grpc:8003')
                stub = produtos_pb2_grpc.ProdutoServiceStub(channel)
                
                # Envia user_id via metadados gRPC
                metadata = [('user_id', user_id)]
                
                req = produtos_pb2.Produto(**grpc_data)
                res = stub.UpdateProduto(req, metadata=metadata)
                
                result = {
                    "action": "update_grpc", 
                    "success": True, 
                    "data": {
                        "mensagem": res.mensagem,
                        "updated_by": user_id,
                        "product_id": grpc_data.get("id")
                    }
                }
            except Exception as grpc_error:
                result = {"action": "update_grpc", "success": False, "error": f"gRPC error: {str(grpc_error)}"}
        
        elif action == "delete_graphql":
            # GraphQL API - constrói mutation query para eliminação
            query = {
                "query": f'''
                    mutation {{
                        deleteProduto(id: {data['id']})
                    }}
                '''
            }
            response = requests.post("http://graphql:8004/graphql", json=query, timeout=10)
            result = {
                "action": "delete_graphql", 
                "success": True, 
                "data": response.json(),
                "deleted_by": user_id
            }
        
        await websocket.send(json.dumps(result))
            
    except Exception as e:
        logger.error(f"Error handling API request {action}: {str(e)}")
        await websocket.send(json.dumps({
            "error": "server_error",
            "error_description": str(e)
        }))

async def handle_legacy_auth(websocket, data):
    """Processa autenticação legada para compatibilidade com versões anteriores"""
    try:
        auth_data = data.get('data', {})
        username = auth_data.get('username')
        password = auth_data.get('password')
        
        if not username or not password:
            await websocket.send(json.dumps({
                "action": "auth",
                "success": False,
                "error": "Missing username or password"
            }))
            return
        
        # Converte para formato OAuth2
        oauth2_data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": "read_product create_product update_product delete_product"
        }
        
        # Utiliza processador OAuth2 existente
        await handle_oauth2_token_request(websocket, oauth2_data)
        
    except Exception as e:
        logger.error(f"Legacy auth error: {str(e)}")
        await websocket.send(json.dumps({
            "action": "auth", 
            "success": False,
            "error": str(e)
        }))

async def handle_websocket(websocket):
    """Gere ligações WebSocket com autenticação OAuth2 + JWT"""
    await register(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                logger.info(f"Received message: {data}")
                
                if "grant_type" in data:
                    # Pedido de token OAuth2
                    await handle_oauth2_token_request(websocket, data)
                elif data.get("action") == "auth":
                    # Formato de autenticação legada
                    await handle_legacy_auth(websocket, data)
                elif "action" in data:
                    # Pedido API (requer autorização OAuth2)
                    action = data["action"]
                    await handle_api_request(websocket, action, data.get("data", {}))
                else:
                    await websocket.send(json.dumps({
                        "error": "invalid_request",
                        "error_description": "Missing grant_type or action"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "error": "invalid_request",
                    "error_description": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error in message handling: {str(e)}")
                await websocket.send(json.dumps({
                    "error": "server_error",
                    "error_description": str(e)
                }))
                
    except websockets.ConnectionClosed:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in websocket handler: {str(e)}")
    finally:
        await unregister(websocket)

def rabbitmq_callback(message):
    """Reencaminha mensagens RabbitMQ para clientes WebSocket"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(notify_clients(message), loop)
        else:
            logger.error("Event loop is not running, cannot notify clients")
    except Exception as e:
        logger.error(f"Error in rabbitmq_callback: {str(e)}")

def start_rabbitmq_consumer():
    """Inicia consumidor RabbitMQ com tentativas de reconexão automática"""
    retry_count = 0
    max_retries = 10
    
    while retry_count < max_retries:
        try:
            logger.info(f"Attempting to connect to RabbitMQ (attempt {retry_count + 1}/{max_retries})")
            credentials = pika.PlainCredentials('admin', 'admin')
            connection = pika.BlockingConnection(
                pika.ConnectionParameters('rabbitmq', credentials=credentials)
            )
            channel = connection.channel()
            channel.queue_declare(queue='product_updates', durable=True)

            def on_message(ch, method, properties, body):
                """Processa mensagens recebidas do RabbitMQ"""
                try:
                    message = json.loads(body)
                    logger.info(f"Received RabbitMQ message: {message}")
                    rabbitmq_callback(message)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Error processing RabbitMQ message: {str(e)}")

            # Configura QoS para processamento sequencial
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='product_updates', on_message_callback=on_message)
            logger.info('RabbitMQ consumer started, waiting for messages...')
            retry_count = 0
            channel.start_consuming()
            
        except Exception as e:
            retry_count += 1
            logger.error(f"RabbitMQ connection error (attempt {retry_count}): {str(e)}")
            if retry_count < max_retries:
                wait_time = min(30, 5 * retry_count)
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("Max retries reached. RabbitMQ consumer will not be available.")
                break

async def main():
    """Função principal que inicia o servidor WebSocket e consumidor RabbitMQ"""
    server = await websockets.serve(handle_websocket, "0.0.0.0", 6789)
    logger.info("OAuth2 + JWT WebSocket server started on ws://0.0.0.0:6789")

    # Inicia consumidor RabbitMQ numa thread separada
    threading.Thread(target=start_rabbitmq_consumer, daemon=True).start()

    await server.wait_closed()

if __name__ == "__main__":
    # Executa o servidor se o script for executado directamente
    asyncio.run(main())
