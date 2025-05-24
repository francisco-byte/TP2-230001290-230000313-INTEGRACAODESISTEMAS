# 🧠 Projeto: Sistema Cliente-Servidor para Gestão de Produtos com Múltiplas APIs e Interface Gráfica

Este projeto consiste numa aplicação cliente-servidor desenvolvida em Python que permite gerir uma lista de produtos. A aplicação oferece funcionalidades para **visualizar, adicionar, remover e atualizar produtos**, sendo que cada produto possui um **ID, nome, preço e quantidade em stock**.

O servidor disponibiliza diferentes formas de acesso aos dados através de múltiplas tecnologias: **REST, SOAP, gRPC e GraphQL**. O cliente comunica com o servidor através de uma **interface gráfica desenvolvida em Tkinter**, permitindo ao utilizador escolher o tipo de serviço a utilizar para realizar as operações CRUD (Create, Read, Update, Delete).

---

## 🗂️ Estrutura do Projeto

```
.
├── cliente/                   # Interface gráfica Tkinter
│   ├── cliente.py
│   ├── produtos_pb2_grpc.py   # Define os serviços
│   └── produtos_pb2.py        # Define os produtos
|
├── servidor/                 # Implementação dos serviços
│   ├── rest/
│   │   ├── app.py             # API REST
│   │   ├── Dockerfile.rest    
│   │   └── requirements.txt
│   ├── soap/
│   │   ├── app.py             # API SOAP
│   │   ├── Dockerfile.soap    
│   │   ├── schema.xsd         
│   │   └── requirements.txt
│   ├── grpc/
│   │   ├── app.py             # Servidor gRPC
│   │   ├── produtos.proto     
│   │   ├── produtos_pb2_grpc.py
│   │   ├── produtos_pb2.py
│   │   ├── Dockerfile.grpc    
│   │   └── requirements.txt
│   ├── graphql/
│   │   ├── graphql_delete.py  # API GraphQL
│   │   ├── Dockerfile.graphql 
│   │   └── requirements.txt
│   └── shared/
│       ├── produtos.json      # Dados persistentes
│       └── schema.json
├── documentacao/
│   └── README.md              # Este ficheiro
└── docker-compose.yml         # Orquestração dos serviços
```

---

## 🚀 Tecnologias Utilizadas

- Python 3.10+
- FastAPI (REST)
- Uvicorn (ASGI)
- Flask (REST)
- Spyne (SOAP)
- gRPC + Protobuf (RPC)
- Strawberry (GraphQL)
- Tkinter (GUI)
- JSON (Persistência)
- Docker & Docker Compose

---

## ⚙️ Como Correr o Projeto

### 🔧 Pré-requisitos

- Docker
- Python 3.10+

### ▶️ Com Docker

```bash
docker-compose up --build
```

### 🧪 Manualmente

#### 1. Servidores

```bash
# REST
cd servidor/rest
python app.py

# SOAP
cd servidor/soap
python app.py

# gRPC
cd servidor/grpc
python app.py

# GraphQL
cd servidor/graphql
python graphql_delete.py
```

#### 2. Cliente

```bash
cd cliente
python cliente.py
```

---

## 📡 Funcionalidades por API

| Tecnologia | Tipo de API | Operação  |
|------------|-------------|-----------|
| REST       | HTTP (JSON) | **Create Produto** |
| SOAP       | XML (WSDL)  | **Read Produto**   |
| gRPC       | Protobuf    | **Update Produto** |
| GraphQL    | Query/Mutation | **Remove Produto** |

---

## 📚 Detalhes dos Endpoints

### 🟩 REST - Criar Produto

- **URL**: `http://localhost:8001/create`
- **Método**: `POST`
- **Body**:
  ```json
  {
    "id": 1,
    "name": "Produto Exemplo",
    "price": 20.5,
    "stock": 100
  }
  ```
- **Resposta**:
  ```json
  {
    "mensagem": "Produto Produto Exemplo criado com sucesso!"
  }
  ```

---

### 🟦 SOAP - Listar Todos os Produtos

- **URL**: `http://localhost:8002/?wsdl`
- **Operação**: `read_all()`
- **Resposta**: JSON como string:
  ```json
  [
    {
      "id": 1,
      "name": "Produto Exemplo",
      "price": 20.5,
      "stock": 100
    }
  ]
  ```

---

### 🟨 gRPC - Atualizar Produto

- **Host**: `localhost:8003`
- **Serviço**: `UpdateProduto`
- **Protobuf**:
  ```proto
  message Produto {
      int32 id = 1;
      string name = 2;
      double price = 3;
      int32 stock = 4;
  }

  message Resposta {
      string mensagem = 1;
  }

  service ProdutoService {
      rpc UpdateProduto(Produto) returns (Resposta);
  }
  ```
- **Exemplo de uso em Python**:
  ```python
  produto = produtos_pb2.Produto(id=1, name="Atualizado", price=99.0, stock=10)
  resposta = stub.UpdateProduto(produto)
  print(resposta.mensagem)
  ```

---

### 🟥 GraphQL - Remover Produto

- **URL**: `http://localhost:8004/graphql`
- **Mutation**:
  ```graphql
  mutation {
    deleteProduto(id: 1)
  }
  ```
- **Resposta**:
  ```json
  {
    "data": {
      "deleteProduto": "Produto com ID 1 removido com sucesso."
    }
  }
  ```

---

## 🖥️ Cliente Tkinter

Interface gráfica desenvolvida em `Tkinter` que permite utilizar as 4 APIs com os seguintes botões:

| Ação             | Tecnologia | Função Tkinter              |
|------------------|------------|-----------------------------|
| Criar Produto    | REST       | `criar_produto_rest()`      |
| Mostrar Produtos | SOAP       | `listar_produtos_soap()`    |
| Atualizar Produto| gRPC       | `atualizar_produto_grpc()`  |
| Remover Produto  | GraphQL    | `remover_produto_graphql()` |

---

## 📦 Docker Compose

```yaml
services:
  rest:
    build: ./Servidor/REST
    ports:
      - "8001:8001"
    volumes:
      - ./Servidor/shared:/shared  
  soap:
    build: ./Servidor/SOAP
    ports:
      - "8002:8002"
    volumes:
      - ./Servidor/shared:/shared  
  graphql:
    build: ./Servidor/GraphQL
    ports:
      - "8004:8004"
    volumes:
      - ./Servidor/shared:/shared  
  grpc:
    build: ./Servidor/GRPC
    ports:
      - "8003:8003"
    volumes:
      - ./Servidor/shared:/shared  
  shared:
    image: alpine
    volumes:
      - ./Servidor/shared:/shared
    command: tail -f /dev/null
```


🎥 Demonstração em Vídeo
Dentro da pasta documentacao/ encontra-se um vídeo demonstrativo que mostra o funcionamento completo da aplicação, incluindo a interação com todas as APIs através da interface gráfica.


---

## 👤 Autores

Projeto desenvolvido por **Francisco Carvalho dos Reis** e **Ricardo Félix da Silva**, no contexto da disciplina de **Integração de Sistemas** do Instituto Politécnico de Santarém.

---
