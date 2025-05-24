from flask import Flask, request, jsonify
import json
import os
from jsonschema import validate, ValidationError
from pymongo import MongoClient
from bson import ObjectId
import pika

app = Flask(__name__)

# MongoDB connection
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), 'schema.json')

def carregar_schema():
    """Carrega o schema JSON para validação."""
    with open(SCHEMA_FILE, 'r') as f:
        return json.load(f)

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

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'REST service is running', 'port': 8001})

@app.route('/create', methods=['POST'])
def create_produto():
    """Cria um novo produto no MongoDB."""
    try:
        produto = request.json
        
        # Validar o produto contra o schema
        schema = carregar_schema()
        validate(instance=produto, schema=schema)
        
        # Verificar se já existe produto com mesmo ID
        if collection.find_one({'id': produto['id']}):
            return jsonify({'erro': 'ID ja existente'}), 400

        # Inserir produto no MongoDB
        result = collection.insert_one(produto)
        
        # Send RabbitMQ notification
        notification = {
            'action': 'create',
            'produto': produto,
            'timestamp': str(result.inserted_id)
        }
        send_rabbitmq_notification(notification)
        
        return jsonify({'mensagem': f"Produto {produto['name']} criado com sucesso!", 'mongodb_id': str(result.inserted_id)})
    except ValidationError as e:
        return jsonify({'erro': f'Dados invalidos: {e.message}'}), 400
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
