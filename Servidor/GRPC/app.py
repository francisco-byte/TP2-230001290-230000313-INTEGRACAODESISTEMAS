import grpc
from concurrent import futures
import produtos_pb2
import produtos_pb2_grpc
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

class ProdutoService(produtos_pb2_grpc.ProdutoServiceServicer):
    def UpdateProduto(self, request, context):
        # Atualizar produto no MongoDB
        result = collection.update_one(
            {'id': request.id},
            {'$set': {
                'id': request.id,
                'name': request.name,
                'price': request.price,
                'stock': request.stock
            }}
        )
        
        if result.matched_count == 0:
            return produtos_pb2.Resposta(mensagem="Produto com ID não encontrado.")
        
        return produtos_pb2.Resposta(mensagem="Produto atualizado com sucesso.")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    produtos_pb2_grpc.add_ProdutoServiceServicer_to_server(ProdutoService(), server)
    server.add_insecure_port('[::]:8003')
    print("gRPC server online em porta 8003")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
