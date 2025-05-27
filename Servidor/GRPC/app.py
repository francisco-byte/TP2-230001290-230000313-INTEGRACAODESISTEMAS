import grpc
from concurrent import futures
import produtos_pb2
import produtos_pb2_grpc
from pymongo import MongoClient
from bson import ObjectId
import json
import pika

# MongoDB connection
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

def send_rabbitmq_notification(message):
    """Send notification to RabbitMQ"""
    try:
        credentials = pika.PlainCredentials('admin', 'admin')
        connection = pika.BlockingConnection(
            pika.ConnectionParameters('rabbitmq', credentials=credentials)
        )
        channel = connection.channel()
        channel.queue_declare(queue='product_updates', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='product_updates',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
    except Exception as e:
        print(f"Error sending RabbitMQ notification: {e}")

class ProdutoService(produtos_pb2_grpc.ProdutoServiceServicer):
    def UpdateProduto(self, request, context):
        # Get user_id from gRPC metadata (if provided by WebSocket)
        metadata = dict(context.invocation_metadata())
        user_id = metadata.get('user_id', 'grpc_user')
        
        # Atualizar produto no MongoDB
        update_data = {
            'id': request.id,
            'name': request.name,
            'price': request.price,
            'stock': request.stock,
            'updated_by': user_id  # Track who updated it
        }
        
        result = collection.update_one(
            {'id': request.id},
            {'$set': update_data}
        )
        
        if result.matched_count == 0:
            return produtos_pb2.Resposta(mensagem="Produto com ID não encontrado.")
        
        # Send RabbitMQ notification
        notification = {
            'action': 'update',
            'produto_id': request.id,
            'user_id': user_id,
            'timestamp': str(ObjectId())
        }
        send_rabbitmq_notification(notification)
        
        return produtos_pb2.Resposta(mensagem=f"Produto atualizado com sucesso por {user_id}.")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    produtos_pb2_grpc.add_ProdutoServiceServicer_to_server(ProdutoService(), server)
    server.add_insecure_port('[::]:8003')
    print("gRPC server online em porta 8003")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
