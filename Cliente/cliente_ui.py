import tkinter as tk
import json
import threading
import websocket
import time

# Global WebSocket connection
ws_connection = None

def get_input():
    return {
        "id": int(entry_id.get()),
        "name": entry_nome.get(),
        "price": float(entry_preco.get()),
        "stock": int(entry_stock.get())
    }

def send_ws_request(action, data=None):
    """Send request through WebSocket"""
    if ws_connection:
        message = {
            "action": action,
            "data": data or {}
        }
        try:
            ws_connection.send(json.dumps(message))
        except Exception as e:
            mostrar_resposta({"erro": f"WebSocket send error: {str(e)}"})
    else:
        mostrar_resposta({"erro": "WebSocket not connected"})

def criar_produto_rest():
    produto = get_input()
    send_ws_request("create_rest", produto)

def listar_produtos_soap():
    send_ws_request("list_soap")

def atualizar_produto_grpc():
    produto = get_input()
    send_ws_request("update_grpc", produto)

def remover_produto_graphql():
    id_produto = int(entry_id.get())
    send_ws_request("delete_graphql", {"id": id_produto})

def mostrar_resposta(data):
    # Schedule UI update on the main thread
    if root:
        root.after(0, lambda d=data: (
            text_output.delete(1.0, tk.END),
            text_output.insert(tk.END, json.dumps(d, indent=2))
        ))

def update_ws_status(status):
    # Schedule UI update on the main thread
    if root:
        root.after(0, lambda s=status: ws_status_var.set(s))

def on_message(ws, message):
    try:
        data = json.loads(message)
        if "action" in data:
            # API response
            mostrar_resposta(data)
        else:
            # Other messages (notifications, etc.)
            mostrar_resposta({"websocket_update": data})
    except Exception as e:
        mostrar_resposta({"erro": f"Message parse error: {str(e)}"})

def on_error(ws, error):
    mostrar_resposta({"websocket_error": str(error)})
    update_ws_status("Error")

def on_close(ws, close_status_code, close_msg):
    mostrar_resposta({"websocket_closed": f"Code: {close_status_code}, Message: {close_msg}"})
    update_ws_status("Closed")
    # Attempt to reconnect
    threading.Timer(5.0, start_websocket).start()

def on_open(ws):
    global ws_connection
    ws_connection = ws
    mostrar_resposta({"websocket": "Connection opened"})
    update_ws_status("Connected")

def start_websocket():
    global ws_connection
    try:
        ws = websocket.WebSocketApp("ws://localhost:6789/",
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        ws.on_open = on_open
        ws.run_forever()
    except Exception as e:
        update_ws_status(f"Connection failed: {str(e)}")
        # Retry connection after 5 seconds
        threading.Timer(5.0, start_websocket).start()

# ----------------- UI -----------------
root = tk.Tk()
root.title("Gestor de Produtos - Integração via WebSocket")

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

# Status Labels
ws_status_var = tk.StringVar(value="Disconnected")

tk.Label(root, text="WebSocket Status:").grid(row=6, column=0, sticky="w")
tk.Label(root, textvariable=ws_status_var).grid(row=6, column=1, sticky="w")

# Resultado
text_output = tk.Text(root, height=15, width=60)
text_output.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

# Start WebSocket client in a separate thread
ws_thread = threading.Thread(target=start_websocket)
ws_thread.daemon = True
ws_thread.start()

root.mainloop()