import asyncio
import websockets
import json
import pika
import threading
import logging
import time
import requests
from websocket_auth import OAuth2JWTAuthenticator, OAuth2Provider

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OAuth2 + JWT setup
jwt_auth = OAuth2JWTAuthenticator("your-super-secret-jwt-key-change-in-production")
oauth2_provider = OAuth2Provider()
connected_clients = {}

async def notify_clients(message):
    if connected_clients:
        message_data = json.dumps(message)
        # Only notify authenticated clients
        authenticated_clients = [ws for ws, info in connected_clients.items() 
                               if info.get('authenticated', False)]
        if authenticated_clients:
            await asyncio.gather(
                *[client.send(message_data) for client in authenticated_clients],
                return_exceptions=True
            )

async def register(websocket):
    connected_clients[websocket] = {'authenticated': False}
    logger.info(f"Client connected: {websocket.remote_address}")
    await websocket.send(json.dumps({
        "status": "connected",
        "message": "OAuth2 authentication required",
        "auth_endpoint": "/auth",
        "supported_grant_types": ["password", "refresh_token"]
    }))

async def unregister(websocket):
    if websocket in connected_clients:
        client_info = connected_clients[websocket]
        if client_info.get('authenticated'):
            logger.info(f"OAuth2 user {client_info.get('user_id')} disconnected")
        del connected_clients[websocket]
    logger.info(f"Client disconnected: {websocket.remote_address}")

async def handle_oauth2_token_request(websocket, data):
    """Handle OAuth2 token request (RFC 6749)"""
    try:
        grant_type = data.get('grant_type')
        
        if grant_type == 'password':
            # OAuth2 Resource Owner Password Credentials Grant
            username = data.get('username')
            password = data.get('password')
            scope = data.get('scope', 'read_product')  # OAuth2 scope
            
            if not username or not password:
                await websocket.send(json.dumps({
                    "error": "invalid_request",
                    "error_description": "Missing username or password"
                }))
                return
            
            user_data = await oauth2_provider.authenticate_user_password_grant(username, password, scope)
            if user_data:
                # Generate OAuth2 tokens
                access_token = jwt_auth.generate_access_token(
                    user_data['user_id'],
                    user_data['email'], 
                    user_data['roles'],
                    user_data['permissions']
                )
                refresh_token = jwt_auth.generate_refresh_token(user_data['user_id'])
                
                # Store authenticated client
                connected_clients[websocket] = {
                    'authenticated': True,
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'roles': user_data['roles'],
                    'permissions': user_data['permissions'],
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }
                
                # OAuth2 token response (RFC 6749)
                await websocket.send(json.dumps({
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 86400,  # 24 hours
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
            # OAuth2 Refresh Token Grant
            refresh_token = data.get('refresh_token')
            
            if not refresh_token:
                await websocket.send(json.dumps({
                    "error": "invalid_request", 
                    "error_description": "Missing refresh_token"
                }))
                return
            
            user_data = await oauth2_provider.refresh_token_grant(refresh_token, jwt_auth)
            if user_data:
                new_access_token = jwt_auth.generate_access_token(
                    user_data['user_id'],
                    user_data['email'],
                    user_data['roles'], 
                    user_data['permissions']
                )
                
                # Update client info with new token
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
    """Verify OAuth2 Bearer token and scope"""
    client_info = connected_clients.get(websocket)
    if not client_info or not client_info.get('authenticated'):
        return False, "access_denied", "Authentication required"
    
    # Verify JWT access token
    access_token = client_info.get('access_token')
    if access_token:
        payload = jwt_auth.verify_access_token(access_token)
        if not payload:
            return False, "invalid_token", "Access token expired or invalid"
        
        # Check OAuth2 scope
        if jwt_auth.check_scope_permission(payload, required_scope):
            return True, None, None
        else:
            return False, "insufficient_scope", f"Required scope: {required_scope}"
    
    return False, "invalid_token", "No access token provided"

async def handle_api_request(websocket, action, data):
    """Handle API requests with OAuth2 authorization"""
    try:
        # OAuth2 scope mapping
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
        
        # Verify OAuth2 authorization
        authorized, error_code, error_description = await verify_bearer_token(websocket, required_scope)
        if not authorized:
            await websocket.send(json.dumps({
                "error": error_code,
                "error_description": error_description,
                "required_scope": required_scope
            }))
            return

        # Get user context
        client_info = connected_clients.get(websocket, {})
        user_id = client_info.get('user_id', 'unknown_user')

        # Execute API calls
        if action == "create_rest":
            # REST can handle user_id field directly
            data['user_id'] = user_id
            response = requests.post("http://rest:8001/create", json=data, timeout=10)
            result = {"action": "create_rest", "success": True, "data": response.json()}
        
        elif action == "list_soap":
            try:
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
                import grpc
                import produtos_pb2
                import produtos_pb2_grpc
                
                # Filter data to only include fields that gRPC Produto message expects
                grpc_data = {
                    "id": data.get("id"),
                    "name": data.get("name"), 
                    "price": data.get("price"),
                    "stock": data.get("stock")
                }
                
                # Remove None values
                grpc_data = {k: v for k, v in grpc_data.items() if v is not None}
                
                channel = grpc.insecure_channel('grpc:8003')
                stub = produtos_pb2_grpc.ProdutoServiceStub(channel)
                
                # Send user_id via gRPC metadata
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
    """Handle legacy authentication format for backward compatibility"""
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
        
        # Convert to OAuth2 format
        oauth2_data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": "read_product create_product update_product delete_product"
        }
        
        # Use existing OAuth2 handler
        await handle_oauth2_token_request(websocket, oauth2_data)
        
    except Exception as e:
        logger.error(f"Legacy auth error: {str(e)}")
        await websocket.send(json.dumps({
            "action": "auth", 
            "success": False,
            "error": str(e)
        }))

async def handle_websocket(websocket):
    """Handle WebSocket connections with OAuth2 + JWT"""
    await register(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                logger.info(f"Received message: {data}")
                
                if "grant_type" in data:
                    # OAuth2 token request
                    await handle_oauth2_token_request(websocket, data)
                elif data.get("action") == "auth":
                    # Legacy authentication format
                    await handle_legacy_auth(websocket, data)
                elif "action" in data:
                    # API request (requires OAuth2 authorization)
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
    """Forward RabbitMQ message to WebSocket clients"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(notify_clients(message), loop)
        else:
            logger.error("Event loop is not running, cannot notify clients")
    except Exception as e:
        logger.error(f"Error in rabbitmq_callback: {str(e)}")

def start_rabbitmq_consumer():
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
                try:
                    message = json.loads(body)
                    logger.info(f"Received RabbitMQ message: {message}")
                    rabbitmq_callback(message)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Error processing RabbitMQ message: {str(e)}")

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
    server = await websockets.serve(handle_websocket, "0.0.0.0", 6789)
    logger.info("OAuth2 + JWT WebSocket server started on ws://0.0.0.0:6789")

    threading.Thread(target=start_rabbitmq_consumer, daemon=True).start()

    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
