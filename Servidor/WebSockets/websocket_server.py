import asyncio
import websockets
import json
import pika
import threading
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connected_clients = set()

async def notify_clients(message):
    if connected_clients:
        message_data = json.dumps(message)
        # Use asyncio.gather instead of asyncio.wait for better error handling
        if connected_clients:
            await asyncio.gather(
                *[client.send(message_data) for client in connected_clients],
                return_exceptions=True
            )

async def register(websocket):
    connected_clients.add(websocket)
    logger.info(f"Client connected: {websocket.remote_address}")
    await websocket.send(json.dumps({"status": "connected"}))

async def unregister(websocket):
    if websocket in connected_clients:
        connected_clients.remove(websocket)
    logger.info(f"Client disconnected: {websocket.remote_address}")

async def handle_api_request(action, data):
    """Handle API requests through WebSocket"""
    try:
        if action == "create_rest":
            import requests
            response = requests.post("http://rest:8001/create", json=data, timeout=10)
            return {"action": "create_rest", "success": True, "data": response.json()}
        
        elif action == "list_soap":
            from zeep import Client as SoapClient
            client = SoapClient("http://soap:8002/?wsdl")
            produtos = client.service.read_all()
            return {"action": "list_soap", "success": True, "data": json.loads(produtos)}
        
        elif action == "update_grpc":
            # Now we can use the actual gRPC implementation
            try:
                import grpc
                import produtos_pb2
                import produtos_pb2_grpc
                
                channel = grpc.insecure_channel('grpc:8003')
                stub = produtos_pb2_grpc.ProdutoServiceStub(channel)
                req = produtos_pb2.Produto(**data)
                res = stub.UpdateProduto(req)
                return {"action": "update_grpc", "success": True, "data": {"mensagem": res.mensagem}}
            except Exception as grpc_error:
                return {"action": "update_grpc", "success": False, "error": f"gRPC error: {str(grpc_error)}"}
        
        elif action == "delete_graphql":
            import requests
            query = {
                "query": f'''
                    mutation {{
                        deleteProduto(id: {data['id']})
                    }}
                '''
            }
            response = requests.post("http://graphql:8004/graphql", json=query, timeout=10)
            return {"action": "delete_graphql", "success": True, "data": response.json()}
        
        else:
            return {"action": action, "success": False, "error": "Unknown action"}
            
    except Exception as e:
        logger.error(f"Error handling API request {action}: {str(e)}")
        return {"action": action, "success": False, "error": str(e)}

async def handle_websocket(websocket):
    """Handle individual WebSocket connections"""
    await register(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                logger.info(f"Received message from client: {data}")
                
                if "action" in data:
                    # Handle API requests
                    result = await handle_api_request(data["action"], data.get("data", {}))
                    await websocket.send(json.dumps(result))
                else:
                    # Echo back for other messages
                    await websocket.send(json.dumps({"echo": data}))
                    
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
            retry_count = 0  # Reset retry count on successful connection
            channel.start_consuming()
            
        except Exception as e:
            retry_count += 1
            logger.error(f"RabbitMQ connection error (attempt {retry_count}): {str(e)}")
            if retry_count < max_retries:
                wait_time = min(30, 5 * retry_count)  # Exponential backoff, max 30s
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("Max retries reached. RabbitMQ consumer will not be available.")
                break

async def main():
    # Start WebSocket server with the new handler approach
    server = await websockets.serve(handle_websocket, "0.0.0.0", 6789)
    logger.info("WebSocket server started on ws://0.0.0.0:6789")

    # Start RabbitMQ consumer in a separate thread
    threading.Thread(target=start_rabbitmq_consumer, daemon=True).start()

    # Keep the server running
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
