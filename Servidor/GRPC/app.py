import grpc
from concurrent import futures
import produtos_pb2
import produtos_pb2_grpc
from pymongo import MongoClient
from bson import ObjectId
import json
import pika

# Ligação à base de dados MongoDB
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

def send_rabbitmq_notification(message):
    """Envia notificação para o RabbitMQ após operação de actualização"""
    try:
        # Configura credenciais de autenticação para RabbitMQ
        credentials = pika.PlainCredentials('admin', 'admin')
        connection = pika.BlockingConnection(
            pika.ConnectionParameters('rabbitmq', credentials=credentials)
        )
        channel = connection.channel()
        
        # Declara fila durável para actualizações de produtos
        channel.queue_declare(queue='product_updates', durable=True)
        
        # Publica mensagem na fila com persistência
        channel.basic_publish(
            exchange='',
            routing_key='product_updates',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # Torna a mensagem persistente
        )
        connection.close()
    except Exception as e:
        print(f"Error sending RabbitMQ notification: {e}")

class ProdutoService(produtos_pb2_grpc.ProdutoServiceServicer):
    """Classe de serviço gRPC que implementa as operações de produtos"""
    
    def UpdateProduto(self, request, context):
        """
        Actualiza um produto existente na base de dados MongoDB
        
        Args:
            request: Objecto de pedido gRPC com dados do produto
            context: Contexto da chamada gRPC (contém metadados)
            
        Returns:
            produtos_pb2.Resposta: Mensagem de confirmação ou erro
        """
        # Obtém user_id dos metadados gRPC (se fornecido pelo WebSocket)
        metadata = dict(context.invocation_metadata())
        user_id = metadata.get('user_id', 'grpc_user')
        
        # Prepara dados para actualização no MongoDB
        update_data = {
            'id': request.id,
            'name': request.name,
            'price': request.price,
            'stock': request.stock,
            'updated_by': user_id  # Regista quem fez a actualização
        }
        
        # Executa actualização na base de dados
        result = collection.update_one(
            {'id': request.id},  # Critério de pesquisa pelo ID
            {'$set': update_data}  # Dados a actualizar
        )
        
        # Verifica se algum documento foi encontrado e actualizado
        if result.matched_count == 0:
            return produtos_pb2.Resposta(mensagem="Produto com ID não encontrado.")
        
        # Prepara notificação para enviar ao sistema de mensagens
        notification = {
            'action': 'update',
            'produto_id': request.id,
            'user_id': user_id,
            'timestamp': str(ObjectId())  # Timestamp baseado em ObjectId do MongoDB
        }
        
        # Envia notificação assíncrona via RabbitMQ
        send_rabbitmq_notification(notification)
        
        return produtos_pb2.Resposta(mensagem=f"Produto atualizado com sucesso por {user_id}.")

def serve():
    """Inicia o servidor gRPC e configura o serviço de produtos"""
    # Cria servidor gRPC com pool de threads para concorrência
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Regista o serviço de produtos no servidor
    produtos_pb2_grpc.add_ProdutoServiceServicer_to_server(ProdutoService(), server)
    
    # Configura porta de escuta (sem encriptação para desenvolvimento)
    server.add_insecure_port('[::]:8003')
    
    print("gRPC server online em porta 8003")
    
    # Inicia o servidor e aguarda terminação
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    # Executa o servidor se o script for executado directamente
    serve()
