# 🧠 Sistema Cliente-Servidor para Gestão de Produtos com Múltiplas APIs e Interface Gráfica

Este projeto consiste numa aplicação cliente-servidor desenvolvida em Python que permite gerir uma lista de produtos de forma distribuída. A aplicação oferece funcionalidades para **visualizar, adicionar, remover e atualizar produtos**, sendo que cada produto possui um **ID, nome, preço e quantidade em stock**.

O sistema utiliza uma arquitetura distribuída com **servidores em máquinas separadas** e oferece diferentes formas de acesso aos dados através de múltiplas tecnologias: **REST, SOAP, gRPC, GraphQL e WebSockets**. O cliente comunica com os servidores através de uma **interface gráfica desenvolvida em Tkinter com acesso remoto via SSH**.

---

## 👥 Autores

Projeto desenvolvido por:
- **Francisco Carvalho dos Reis**
- **Ricardo Félix da Silva**

**Contexto**: Disciplina de Integração de Sistemas - Instituto Politécnico de Santarém

---

## 🏗️ Arquitetura Distribuída

O sistema é composto por múltiplos servidores especializados distribuídos em duas máquinas:

- **Servidor (192.168.246.46)**: Executa todos os serviços backend (REST, SOAP, gRPC, GraphQL, WebSockets)
- **Cliente (192.168.246.44)**: Executa a interface gráfica Tkinter com acesso remoto via SSH

### Componentes da Arquitetura:
- **MongoDB**: Base de dados NoSQL para persistência dos produtos
- **RabbitMQ**: Sistema de mensagens para comunicação assíncrona entre serviços
- **OAuth2 + JWT**: Sistema de autenticação e autorização
- **Docker Compose**: Orquestração de todos os serviços backend
- **XMING + SSH**: Acesso remoto à interface gráfica

---

## 🗂️ Estrutura do Projeto

```
.
├── Cliente/                   # Interface gráfica Tkinter (máquina .44)
│   ├── cliente_ui.py          # Interface principal
│   ├── produtos_pb2_grpc.py   # Definições gRPC
│   └── produtos_pb2.py        # Protobuf gerado
│
├── Servidor/                  # Serviços backend (máquina .46)
│   ├── REST/
│   │   ├── app.py             # API REST com FastAPI
│   │   ├── Dockerfile         
│   │   └── requirements.txt
│   ├── SOAP/
│   │   ├── app.py             # API SOAP com Spyne
│   │   ├── Dockerfile         
│   │   ├── schema.xsd         
│   │   └── requirements.txt
│   ├── GRPC/
│   │   ├── app.py             # Servidor gRPC
│   │   ├── produtos.proto     
│   │   ├── produtos_pb2_grpc.py
│   │   ├── produtos_pb2.py
│   │   ├── Dockerfile         
│   │   └── requirements.txt
│   ├── GraphQL/
│   │   ├── app.py             # API GraphQL com Strawberry
│   │   ├── Dockerfile         
│   │   └── requirements.txt
│   ├── RabbitMQ/              
│   │   ├── Dockerfile             
│   │   └── rabbitmq_integration.py
│   └── WebSockets/
│       ├── websocket_server.py # Servidor WebSocket com OAuth2/JWT
│       ├── websocket_auth.py   # Sistema de autenticação
│       ├── Dockerfile
│       └── requirements.txt
├── docker-compose.yml         # Orquestração completa dos serviços
└── README.md                  # Este documento
```

---

## 🚀 Tecnologias Utilizadas

### Backend
- **Python 3.10+**
- **FastAPI** (REST API)
- **Spyne** (SOAP API)
- **gRPC + Protobuf** (RPC)
- **Strawberry GraphQL** (GraphQL API)
- **WebSockets** (Comunicação em tempo real)
- **MongoDB** (Base de dados NoSQL)
- **RabbitMQ** (Sistema de mensagens)
- **OAuth2 + JWT** (Autenticação e autorização)
- **Docker & Docker Compose** (Containerização)

### Cliente
- **Tkinter** (Interface gráfica)
- **XMING** (Servidor X11 para Windows)
- **SSH** (Acesso remoto)

---

## ⚙️ Como Executar o Projeto

### 🔧 Pré-requisitos

#### Servidor (192.168.246.46)
- Docker
- Docker Compose
- Python 3.10+

#### Cliente (192.168.246.44)
- Python 3.10+
- SSH configurado
- XMING (para acesso gráfico remoto)
- Bibliotecas necessárias (Estão num ficheiro chamado de requirementsClient.txt)

### ▶️ Execução

#### 1. No Servidor (192.168.246.46)

```bash
# Clonar o repositório
git clone <url-do-repositorio>
cd <nome-do-projeto>

# Executar todos os serviços com Docker Compose
docker-compose up --build
```

#### 2. No Cliente (192.168.246.44)

```bash
# No Windows, abrir Command Prompt e configurar o DISPLAY
set DISPLAY=localhost:0.0

# Conectar via SSH com forwarding X11
ssh -Y ubuntu@192.168.246.44

# Clonar o repositório
git clone <url-do-repositorio>
cd <nome-do-projeto>
cd Cliente

# Instalar as bibliotecas
python3 -m pip install requirementsClient.txt

# Executar o cliente gráfico
python3 Cliente/cliente_ui.py
```

---

## 📡 Arquitetura de Serviços

| Tecnologia | Porta | Operação Principal | Descrição |
|------------|-------|-------------------|-----------|
| **REST** | 8001 | Create Produto | API RESTful para criação de produtos |
| **SOAP** | 8002 | Read Produtos | Serviço SOAP para listagem de produtos |
| **gRPC** | 8003 | Update Produto | Serviço gRPC para atualização de produtos |
| **GraphQL** | 8004 | Delete Produto | API GraphQL para remoção de produtos |
| **WebSockets** | 6789 | CRUD Autenticado | Operações em tempo real com autenticação |
| **MongoDB** | 27017 | Base de Dados | Persistência de dados |
| **RabbitMQ** | 5672/15672 | Mensagens | Comunicação assíncrona |

---

## 📚 Detalhes dos Endpoints

### 🟩 REST - Criar Produto

- **URL**: `http://192.168.246.46:8001/create`
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

### 🟦 SOAP - Listar Produtos

- **URL**: `http://192.168.246.46:8002/?wsdl`
- **Operação**: `read_all()`
- **Resposta**: Lista de produtos em formato JSON

### 🟨 gRPC - Atualizar Produto

- **Host**: `192.168.246.46:8003`
- **Serviço**: `UpdateProduto`
- **Protobuf**: Definido em `produtos.proto`

### 🟥 GraphQL - Remover Produto

- **URL**: `http://192.168.246.46:8004/graphql`
- **Mutation**:
  ```graphql
  mutation {
    deleteProduto(id: 1)
  }
  ```

### 🟪 WebSockets - Operações Autenticadas

- **URL**: `ws://192.168.246.46:6789`
- **Autenticação**: OAuth2 + JWT
- **Operações**: CRUD completas em tempo real

---

## 🔐 Sistema de Autenticação

O sistema implementa autenticação OAuth2 com tokens JWT no serviço WebSockets:

- **Fluxos suportados**: Resource Owner Password Credentials Grant e Refresh Token Grant
- **Conformidade**: RFCs 6749 e 7519
- **Características**: Controlo de acesso granular com papéis e permissões
- **Integração**: RabbitMQ para notificações em tempo real

---

## 🔗 Integração e Comunicação

### RabbitMQ
- **Comunicação assíncrona** entre todos os serviços
- **Notificações em tempo real** via WebSockets
- **Arquitetura desacoplada** para escalabilidade

### MongoDB
- **Persistência centralizada** de todos os produtos
- **Acesso através** do servidor REST principalmente
- **Sincronização** via RabbitMQ

---

## 🖥️ Interface Cliente

A interface gráfica Tkinter oferece acesso a todas as APIs:

| Botão | Tecnologia | Função |
|-------|------------|--------|
| Criar Produto | REST | `criar_produto_rest()` |
| Listar Produtos | SOAP | `listar_produtos_soap()` |
| Atualizar Produto | gRPC | `atualizar_produto_grpc()` |
| Remover Produto | GraphQL | `remover_produto_graphql()` |
| Operações WebSocket | WebSockets | `operacoes_websocket()` |

---

## 📦 Configuração Docker Compose

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:4.4
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: produtos_db
    restart: unless-stopped

  rabbitmq:
    image: rabbitmq:3.13-management
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped

  rest:
    build:
      context: ./Servidor
      dockerfile: REST/Dockerfile
    ports:
      - "8001:8001"
    depends_on:
      - mongodb
      - rabbitmq

  soap:
    build:
      context: ./Servidor
      dockerfile: SOAP/Dockerfile
    ports:
      - "8002:8002"
    depends_on:
      - mongodb
      - rabbitmq
      
  graphql:
    build:
      context: ./Servidor
      dockerfile: GraphQL/Dockerfile
    ports:
      - "8004:8004"
    depends_on:
      - mongodb
      - rabbitmq
      
  grpc:
    build:
      context: ./Servidor
      dockerfile: GRPC/Dockerfile
    ports:
      - "8003:8003"
    depends_on:
      - mongodb
      - rabbitmq

  websocket:
    build:
      context: ./Servidor
      dockerfile: WebSockets/Dockerfile
    ports:
      - "6789:6789"
    depends_on:
      - rest
      - soap
      - graphql
      - grpc
      - rabbitmq
    restart: unless-stopped

volumes:
  mongodb_data:
  rabbitmq_data:
```

---

## 🌐 Configuração de Rede

### Servidor (192.168.246.46)
- Executa todos os serviços backend
- MongoDB na porta 27017
- RabbitMQ nas portas 5672 e 15672
- APIs nas portas 8001-8004 e WebSocket na 6789

### Cliente (192.168.246.44)
- Executa apenas a interface gráfica
- Acesso remoto via SSH com X11 forwarding
- Comunicação com servidor via rede

### Acesso Remoto
```bash
# Configurar DISPLAY no Windows
set DISPLAY=localhost:0.0

# Conectar com SSH e X11 forwarding
ssh -Y ubuntu@192.168.246.44

# Executar cliente
python3 Cliente/cliente_ui.py
```

---

## 🔧 Troubleshooting

### Problemas Comuns

1. **Erro de conexão gráfica**:
   - Verificar se XMING está a executar
   - Confirmar configuração `DISPLAY=localhost:0.0`

2. **Falha na conexão com serviços**:
   - Verificar se Docker Compose está a executar no servidor
   - Confirmar conectividade de rede entre máquinas

3. **Erro de autenticação WebSocket**:
   - Verificar tokens JWT
   - Confirmar configuração OAuth2

---

## 🧪 Testes e Monitorização

### RabbitMQ Management
- **URL**: `http://192.168.246.46:15672`
- **Credenciais**: admin/admin
- **Funcionalidade**: Monitorização de filas e mensagens

### MongoDB
- **Porta**: `27017`
- **Base de dados**: `produtos_db`
- **Acesso**: Via clientes MongoDB

---


## 📋 Notas Técnicas

- **Arquitetura**: Microserviços distribuídos
- **Comunicação**: REST, SOAP, gRPC, GraphQL, WebSockets
- **Persistência**: MongoDB
- **Mensagens**: RabbitMQ
- **Autenticação**: OAuth2 + JWT
- **Containerização**: Docker + Docker Compose
- **Interface**: Tkinter com acesso remoto via SSH
