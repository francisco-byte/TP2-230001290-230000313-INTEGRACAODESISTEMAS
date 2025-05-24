import tkinter as tk
import requests
import grpc
import json
from zeep import Client as SoapClient
import produtos_pb2
import produtos_pb2_grpc
import threading
import websocket

def get_input():
    return {
        "id": int(entry_id.get()),
        "name": entry_nome.get(),
        "price": float(entry_preco.get()),
        "stock": int(entry_stock.get())
    }

def criar_produto_rest():
    produto = get_input()
    try:
        res = requests.post("http://localhost/create", json=produto)
        mostrar_resposta(res.json())
    except Exception as e:
        mostrar_resposta({"erro": str(e)})

def listar_produtos_soap():
    try:
        client = SoapClient("http://localhost:8002/?wsdl")
        produtos = client.service.read_all()
        mostrar_resposta(json.loads(produtos))
    except Exception as e:
        mostrar_resposta({"erro": str(e)})

def atualizar_produto_grpc():
    produto = get_input()
    try:
        channel = grpc.insecure_channel('localhost:8003')
        stub = produtos_pb2_grpc.ProdutoServiceStub(channel)
        req = produtos_pb2.Produto(**produto)
        res = stub.UpdateProduto(req)
        mostrar_resposta({"mensagem": res.mensagem})
    except Exception as e:
        mostrar_resposta({"erro": str(e)})

def remover_produto_graphql():
    id_produto = int(entry_id.get())
    try:
        query = {
            "query": f'''
                mutation {{
                    deleteProduto(id: {id_produto})
                }}
            '''
        }
        res = requests.post("http://localhost:8004/graphql", json=query)
        data = res.json()
        mostrar_resposta(data["data"])
    except Exception as e:
        mostrar_resposta({"erro": str(e)})

def mostrar_resposta(data):
    text_output.delete(1.0, tk.END)
    text_output.insert(tk.END, json.dumps(data, indent=2))

def update_ws_status(status):
    ws_status_var.set(status)

def update_rabbitmq_status(status):
    rabbitmq_status_var.set(status)

def on_message(ws, message):
    data = json.loads(message)
    mostrar_resposta({"websocket_update": data})
    # Check for RabbitMQ status in message
    if "rabbitmq_status" in data:
        update_rabbitmq_status(data["rabbitmq_status"])

def on_error(ws, error):
    mostrar_resposta({"websocket_error": str(error)})
    update_ws_status("Error")

def on_close(ws, close_status_code, close_msg):
    mostrar_resposta({"websocket_closed": f"Code: {close_status_code}, Message: {close_msg}"})
    update_ws_status("Closed")

def on_open(ws):
    mostrar_resposta({"websocket": "Connection opened"})
    update_ws_status("Connected")

def start_websocket():
    ws = websocket.WebSocketApp("ws://localhost:6789/",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

# ----------------- UI -----------------
root = tk.Tk()
root.title("Gestor de Produtos - Integração de Sistemas")

tk.Label(root, text="ID").grid(row=0, column=0)
entry_id = tk.Entry(root)
entry_id.grid(row=0, column=1)

tk.Label(root, text="Nome").grid(row=1, column=0)
entry_nome = tk.Entry(root)
entry_nome.grid(row=1, column=1)

tk.Label(root, text="Preço").grid(row=2, column=0)
entry_preco = tk.Entry(root)
entry_preco.grid(row=2, column=1)

tk.Label(root, text="Stock").grid(row=3, column=0)
entry_stock = tk.Entry(root)
entry_stock.grid(row=3, column=1)

# Botões
tk.Button(root, text="Criar (REST)", command=criar_produto_rest).grid(row=4, column=0, pady=10)
tk.Button(root, text="Listar (SOAP)", command=listar_produtos_soap).grid(row=4, column=1)
tk.Button(root, text="Atualizar (gRPC)", command=atualizar_produto_grpc).grid(row=5, column=0)
tk.Button(root, text="Remover (GraphQL)", command=remover_produto_graphql).grid(row=5, column=1)

# Status Labels for WebSocket and RabbitMQ
ws_status_var = tk.StringVar(value="Disconnected")
rabbitmq_status_var = tk.StringVar(value="Unknown")

tk.Label(root, text="WebSocket Status:").grid(row=6, column=0, sticky="w")
tk.Label(root, textvariable=ws_status_var).grid(row=6, column=1, sticky="w")

tk.Label(root, text="RabbitMQ Status:").grid(row=7, column=0, sticky="w")
tk.Label(root, textvariable=rabbitmq_status_var).grid(row=7, column=1, sticky="w")

# Resultado
text_output = tk.Text(root, height=15, width=60)
text_output.grid(row=8, column=0, columnspan=2, padx=10, pady=10)

# Start WebSocket client in a separate thread
ws_thread = threading.Thread(target=start_websocket)
ws_thread.daemon = True
ws_thread.start()

root.mainloop()
