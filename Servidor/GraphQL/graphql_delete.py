import strawberry
import uvicorn
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
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

@strawberry.type
class Query:
    hello: str = "GraphQL Delete Online!"  # dummy query

@strawberry.type
class Mutation:
    @strawberry.mutation
    def delete_produto(self, id: int) -> str:
        # Deletar produto do MongoDB
        result = collection.delete_one({'id': id})
        
        if result.deleted_count == 0:
            return f"Produto com ID {id} não encontrado."
        
        # Send RabbitMQ notification
        notification = {
            'action': 'delete',
            'produto_id': id,
            'timestamp': str(ObjectId())
        }
        send_rabbitmq_notification(notification)
        
        return f"Produto com ID {id} removido com sucesso."

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")

@app.get("/")
def health_check():
    return {"status": "GraphQL service is running", "port": 8004}

if __name__ == "__main__":

    print("GraphQL server online em http://localhost:8004/graphql")
    uvicorn.run("graphql_delete:app", host="0.0.0.0", port=8004, reload=True)
