from spyne import Application, rpc, ServiceBase, Unicode
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
import json
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

class ProdutoReadService(ServiceBase):
    @rpc(_returns=Unicode)
    def read_all(ctx):  # Método para retornar todos os produtos
        # Buscar todos os produtos no MongoDB
        produtos = list(collection.find({}, {'_id': 0}))  # Excluir o campo _id do resultado
        return json.dumps(produtos)  # Retorna os produtos em formato JSON

# Configuração do aplicativo SOAP
application = Application([ProdutoReadService],
    tns='spyne.examples.readproduto',
    in_protocol=Soap11(),
    out_protocol=Soap11(),
)

# Criação da aplicação WSGI para o servidor
wsgi_app = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    # Inicia o servidor SOAP na porta 8002
    server = make_server('0.0.0.0', 8002, wsgi_app)
    print("SOAP server online em http://localhost:8002")
    server.serve_forever()
