import strawberry
import uvicorn
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from pymongo import MongoClient
from bson import ObjectId
import json
import pika

# Ligação à base de dados MongoDB
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

def send_rabbitmq_notification(message):
    """Envia notificação para o RabbitMQ após operação de eliminação"""
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

@strawberry.type
class Query:
    """Classe de consultas GraphQL obrigatória (query fictícia para validação do schema)"""
    hello: str = "GraphQL Delete Online!"  # consulta de demonstração

@strawberry.type
class Mutation:
    """Classe de mutações GraphQL para operações de modificação de dados"""
    
    @strawberry.mutation
    def delete_produto(self, id: int) -> str:
        """
        Elimina um produto da base de dados MongoDB através do seu ID
        
        Args:
            id (int): Identificador único do produto a eliminar
            
        Returns:
            str: Mensagem de confirmação ou erro
        """
        # Tenta eliminar produto do MongoDB pelo ID fornecido
        result = collection.delete_one({'id': id})
        
        # Verifica se algum documento foi eliminado
        if result.deleted_count == 0:
            return f"Produto com ID {id} não encontrado."
        
        # Prepara notificação para enviar ao sistema de mensagens
        notification = {
            'action': 'delete',
            'produto_id': id,
            'timestamp': str(ObjectId())  # Timestamp baseado em ObjectId do MongoDB
        }
        
        # Envia notificação assíncrona via RabbitMQ
        send_rabbitmq_notification(notification)
        
        return f"Produto com ID {id} removido com sucesso."

# Cria schema GraphQL com queries e mutations definidas
schema = strawberry.Schema(query=Query, mutation=Mutation)

# Configura router GraphQL para integração com FastAPI
graphql_app = GraphQLRouter(schema)

# Inicializa aplicação FastAPI
app = FastAPI()

# Integra router GraphQL no endpoint /graphql
app.include_router(graphql_app, prefix="/graphql")

@app.get("/")
def health_check():
    """Endpoint de verificação de estado do serviço"""
    return {"status": "GraphQL service is running", "port": 8004}

if __name__ == "__main__":
    print("GraphQL server online em http://localhost:8004/graphql")
    # Inicia servidor Uvicorn com recarga automática durante desenvolvimento
    uvicorn.run("graphql_delete:app", host="0.0.0.0", port=8004, reload=True)
