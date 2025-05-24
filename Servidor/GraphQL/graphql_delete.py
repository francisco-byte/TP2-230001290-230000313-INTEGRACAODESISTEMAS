import strawberry
import uvicorn
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection
client = MongoClient('mongodb://mongodb:27017/')
db = client['produtos_db']
collection = db['produtos']

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
        
        return f"Produto com ID {id} removido com sucesso."

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")

if __name__ == "__main__":

    print("GraphQL server online em http://localhost:8004/graphql")
    uvicorn.run("graphql_delete:app", port=8004, reload=True)
