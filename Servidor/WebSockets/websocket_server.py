import asyncio
import websockets
import json
import pika
import threading
import logging
import time
import requests

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connected_clients = {}  # Changed to dict to store client info

# Simple authentication without external dependencies
def simple_authenticate(username, password):
    """Simple authentication - no JWT needed"""
    users = {
        "admin": {"password": "admin123", "permissions": ["create", "read", "update", "delete"]},
        "user": {"password": "user123", "permissions": ["create", "read", "update"]},
        "readonly": {"password": "readonly123", "permissions": ["read"]}
    }
    
    user = users.get(username)
    if user and user["password"] == password:
        return user["permissions"]
    return None

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
    connected_clients[websocket] = {'authenticated': False, 'permissions': []}
    logger.info(f"Client connected: {websocket.remote_address}")
    await websocket.send(json.dumps({
        "status": "connected", 
        "message": "Send 'auth' action to authenticate"
    }))

async def unregister(websocket):
    if websocket in connected_clients:
        del connected_clients[websocket]
    logger.info(f"Client disconnected: {websocket.remote_address}")

async def handle_authentication(websocket, data):
    """Handle authentication"""
    username = data.get('username')
    password = data.get('password')
    
    permissions = simple_authenticate(username, password)
    if permissions:
        connected_clients[websocket] = {
            'authenticated': True,
            'username': username,
            'permissions': permissions
        }
        await websocket.send(json.dumps({
            "action": "auth",
            "success": True,
            "message": f"Authenticated as {username}",
            "permissions": permissions
        }))
        logger.info(f"User {username} authenticated")
    else:
        await websocket.send(json.dumps({
            "action": "auth",
            "success": False,
            "message": "Invalid credentials"
        }))

def check_permission(websocket, required_action):
    """Check if user has permission for action"""
    client_info = connected_clients.get(websocket, {})
    if not client_info.get('authenticated'):
        return False, "Not authenticated"
    
    action_permissions = {
        "create_rest": "create",
        "list_soap": "read",
        "update_grpc": "update", 
        "delete_graphql": "delete"
    }
    
    required_perm = action_permissions.get(required_action)
    if required_perm and required_perm in client_info.get('permissions', []):
        return True, None
    
    return False, f"Permission denied. Required: {required_perm}"

async def handle_api_request(websocket, action, data):
    """Handle API requests through WebSocket"""
    try:
        # Check authentication and permissions
        has_permission, error_msg = check_permission(websocket, action)
        if not has_permission:
            await websocket.send(json.dumps({
                "action": action,
                "success": False,
                "error": error_msg
            }))
            return

        if action == "create_rest":
            response = requests.post("http://rest:8001/create", json=data, timeout=10)
            result = {"action": "create_rest", "success": True, "data": response.json()}
        
        elif action == "list_soap":
            try:
                from zeep import Client as SoapClient
                client = SoapClient("http://soap:8002/?wsdl")
                produtos = client.service.read_all()
                result = {"action": "list_soap", "success": True, "data": json.loads(produtos)}
            except Exception as soap_error:
                result = {"action": "list_soap", "success": False, "error": f"SOAP error: {str(soap_error)}"}
        
        elif action == "update_grpc":
            try:
                import grpc
                import produtos_pb2
                import produtos_pb2_grpc
                
                channel = grpc.insecure_channel('grpc:8003')
                stub = produtos_pb2_grpc.ProdutoServiceStub(channel)
                req = produtos_pb2.Produto(**data)
                res = stub.UpdateProduto(req)
                result = {"action": "update_grpc", "success": True, "data": {"mensagem": res.mensagem}}
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
            result = {"action": "delete_graphql", "success": True, "data": response.json()}
        
        else:
            result = {"action": action, "success": False, "error": "Unknown action"}
            
        await websocket.send(json.dumps(result))
            
    except Exception as e:
        logger.error(f"Error handling API request {action}: {str(e)}")
        await websocket.send(json.dumps({
            "action": action,
            "success": False,
            "error": str(e)
        }))

async def handle_websocket(websocket):
    """Handle individual WebSocket connections"""
    await register(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                logger.info(f"Received message from client: {data}")
                
                if "action" in data:
                    action = data["action"]
                    
                    # Handle authentication
                    if action == "auth":
                        await handle_authentication(websocket, data.get("data", {}))
                    else:
                        # Handle API requests
                        await handle_api_request(websocket, action, data.get("data", {}))
                else:
                    await websocket.send(json.dumps({"error": "No action specified"}))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON"}))
            except Exception as e:
                logger.error(f"Error in message handling: {str(e)}")
                await websocket.send(json.dumps({"error": str(e)}))
                
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
    logger.info("WebSocket server started on ws://0.0.0.0:6789")

    threading.Thread(target=start_rabbitmq_consumer, daemon=True).start()

    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
