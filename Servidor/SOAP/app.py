from spyne import Application, rpc, ServiceBase, Unicode
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
import json
import os

# Caminho absoluto para o arquivo 'produtos.json' no contêiner
SHARED_DIR = '/shared'  # Diretório compartilhado mapeado no contêiner
DATA_FILE = os.path.join(SHARED_DIR, 'produtos.json')  # Caminho completo para o arquivo 'produtos.json'

def carregar_dados():
    """Carrega os dados do arquivo 'produtos.json'."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []  # Retorna uma lista vazia caso o arquivo não exista

class ProdutoReadService(ServiceBase):
    @rpc(_returns=Unicode)
    def read_all(ctx):  # Método para retornar todos os produtos
        produtos = carregar_dados()  # Carrega os produtos
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
