from spyne import Application, rpc, ServiceBase, Unicode
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
import json
import pika
from pymongo import MongoClient
from bson import ObjectId

# Ligação à base de dados MongoDB
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

def send_rabbitmq_notification(message):
    """Envia notificação para o RabbitMQ após operação de leitura"""
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

class ProdutoReadService(ServiceBase):
    """Classe de serviço SOAP que implementa operações de leitura de produtos"""
    
    @rpc(_returns=Unicode)
    def read_all(ctx):
        """
        Método SOAP para retornar todos os produtos da base de dados
        
        Returns:
            Unicode: String JSON com todos os produtos ou lista vazia
        """
        # Busca todos os produtos no MongoDB excluindo o campo _id
        produtos = list(collection.find({}, {'_id': 0}))
        
        # Prepara notificação para enviar ao sistema de mensagens
        notification = {
            'action': 'read_all',
            'count': len(produtos),
            'timestamp': str(ObjectId())  # Timestamp baseado em ObjectId do MongoDB
        }
        
        # Envia notificação assíncrona via RabbitMQ
        send_rabbitmq_notification(notification)
        
        return json.dumps(produtos)  # Retorna os produtos em formato JSON

# Configuração da aplicação SOAP com protocolo SOAP 1.1
application = Application([ProdutoReadService],
    tns='spyne.examples.readproduto',  # Target namespace para o serviço SOAP
    in_protocol=Soap11(),              # Protocolo de entrada SOAP 1.1
    out_protocol=Soap11(),             # Protocolo de saída SOAP 1.1
)

# Criação da aplicação WSGI para integração com servidor web
wsgi_app = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    # Inicia o servidor SOAP na porta 8002 acessível externamente
    server = make_server('0.0.0.0', 8002, wsgi_app)
    print("SOAP server online em http://localhost:8002")
    # WSDL disponível em: http://localhost:8002/?wsdl
    server.serve_forever()
