import asyncio
import websockets
import json
import pika
import threading
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connected_clients = set()

async def notify_clients(message):
    if connected_clients:
        message_data = json.dumps(message)
        await asyncio.wait([client.send(message_data) for client in connected_clients])

async def register(websocket):
    connected_clients.add(websocket)
    logger.info(f"Client connected: {websocket.remote_address}")
    # Notify client connected
    await websocket.send(json.dumps({"status": "connected"}))

async def unregister(websocket):
    connected_clients.remove(websocket)
    logger.info(f"Client disconnected: {websocket.remote_address}")

async def handler(websocket, path):
    await register(websocket)
    try:
        async for message in websocket:
            logger.info(f"Received message from client: {message}")
            # Echo back or handle messages if needed
            await websocket.send(json.dumps({"echo": message}))
    except websockets.ConnectionClosed:
        logger.info("Client disconnected")
    finally:
        await unregister(websocket)

def rabbitmq_callback(message):
    # Forward RabbitMQ message to WebSocket clients
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.run_coroutine_threadsafe(notify_clients(message), loop)
    else:
        logger.error("Event loop is not running, cannot notify clients")

def start_rabbitmq_consumer():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='product_updates', durable=True)

    def on_message(ch, method, properties, body):
        message = json.loads(body)
        logger.info(f"Received RabbitMQ message: {message}")
        rabbitmq_callback(message)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='product_updates', on_message_callback=on_message)
    logger.info('RabbitMQ consumer started, waiting for messages...')
    channel.start_consuming()

async def main():
    server = await websockets.serve(handler, "0.0.0.0", 6789)
    logger.info("WebSocket server started on ws://0.0.0.0:6789")

    # Start RabbitMQ consumer in a separate thread
    threading.Thread(target=start_rabbitmq_consumer, daemon=True).start()

    await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
