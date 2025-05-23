import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import json
import os

# Caminho absoluto para o arquivo 'produtos.json' na pasta 'shared'
SHARED_DIR = '/shared'  # Diretório compartilhado mapeado no contêiner
DATA_FILE = os.path.join(SHARED_DIR, 'produtos.json')

def carregar_dados():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def salvar_dados(dados):
    with open(DATA_FILE, 'w') as f:
        json.dump(dados, f, indent=2)

@strawberry.type
class Query:
    hello: str = "GraphQL Delete Online!"  # dummy query

@strawberry.type
class Mutation:
    @strawberry.mutation
    def delete_produto(self, id: int) -> str:
        produtos = carregar_dados()
        novos_produtos = [p for p in produtos if p['id'] != id]

        if len(novos_produtos) == len(produtos):
            return f"Produto com ID {id} não encontrado."

        salvar_dados(novos_produtos)
        return f"Produto com ID {id} removido com sucesso."

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")

if __name__ == "__main__":
    import uvicorn
    print("GraphQL server online em http://localhost:8004/graphql")
    uvicorn.run("graphql_delete:app", port=8004, reload=True)
