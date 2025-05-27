import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import threading
import websocket
import time

# Global variables
ws_connection = None
is_authenticated = False
user_permissions = []
current_user = None

def get_input():
    try:
        return {
            "id": int(entry_id.get()),
            "name": entry_nome.get(),
            "price": float(entry_preco.get()),
            "stock": int(entry_stock.get())
        }
    except ValueError as e:
        raise ValueError(f"Invalid input: {str(e)}")

def authenticate():
    """Handle user authentication"""
    if not ws_connection:
        mostrar_resposta({"error": "WebSocket not connected"})
        return
    
    username = simpledialog.askstring("Login", "Username:")
    password = simpledialog.askstring("Login", "Password:", show='*')
    
    if username and password:
        auth_message = {
            "action": "auth",
            "data": {
                "username": username,
                "password": password
            }
        }
        ws_connection.send(json.dumps(auth_message))

def send_ws_request(action, data=None):
    """Send request through WebSocket"""
    if not ws_connection:
        mostrar_resposta({"erro": "WebSocket not connected"})
        return
        
    if not is_authenticated:
        mostrar_resposta({"erro": "Please authenticate first"})
        return
    
    message = {
        "action": action,
        "data": data or {}
    }
    try:
        ws_connection.send(json.dumps(message))
    except Exception as e:
        mostrar_resposta({"erro": f"WebSocket send error: {str(e)}"})

def criar_produto_rest():
    try:
        produto = get_input()
        send_ws_request("create_rest", produto)
    except ValueError as e:
        mostrar_resposta({"error": str(e)})

def listar_produtos_soap():
    send_ws_request("list_soap")

def atualizar_produto_grpc():
    try:
        produto = get_input()
        send_ws_request("update_grpc", produto)
    except ValueError as e:
        mostrar_resposta({"error": str(e)})

def remover_produto_graphql():
    try:
        id_produto = int(entry_id.get())
        send_ws_request("delete_graphql", {"id": id_produto})
    except ValueError:
        mostrar_resposta({"error": "ID must be a number"})

def mostrar_resposta(data):
    if root:
        root.after(0, lambda d=data: (
            text_output.delete(1.0, tk.END),
            text_output.insert(tk.END, json.dumps(d, indent=2))
        ))

def update_ws_status(status):
    if root:
        root.after(0, lambda s=status: ws_status_var.set(s))

def update_auth_status(status):
    if root:
        root.after(0, lambda s=status: auth_status_var.set(s))

def update_user_info(user_info):
    if root:
        root.after(0, lambda info=user_info: user_info_var.set(info))

def on_message(ws, message):
    global is_authenticated, user_permissions, current_user
    
    try:
        data = json.loads(message)
        
        if data.get("action") == "auth":
            if data.get("success"):
                is_authenticated = True
                current_user = data.get("message", "").replace("Authenticated as ", "")
                user_permissions = data.get("permissions", [])
                
                update_auth_status("Authenticated")
                update_user_info(f"User: {current_user}")
                mostrar_resposta({
                    "authentication": "Success",
                    "user": current_user,
                    "permissions": user_permissions
                })
            else:
                is_authenticated = False
                update_auth_status("Failed")
                update_user_info("Not logged in")
                mostrar_resposta({"authentication": "Failed", "message": data.get("message")})
                
        elif "action" in data:
            # API response
            mostrar_resposta(data)
        else:
            # Other messages (notifications, etc.)
            mostrar_resposta({"websocket_update": data})
            
    except json.JSONDecodeError:
        mostrar_resposta({"websocket_message": message})
    except Exception as e:
        mostrar_resposta({"erro": f"Message parse error: {str(e)}"})

def on_error(ws, error):
    mostrar_resposta({"websocket_error": str(error)})
    update_ws_status("Error")

def on_close(ws, close_status_code, close_msg):
    global is_authenticated, user_permissions, current_user
    
    is_authenticated = False
    user_permissions = []
    current_user = None
    
    mostrar_resposta({"websocket_closed": f"Code: {close_status_code}, Message: {close_msg}"})
    update_ws_status("Closed")
    update_auth_status("Not Authenticated")
    update_user_info("Not logged in")
    
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
        threading.Timer(5.0, start_websocket).start()

# ----------------- UI -----------------
root = tk.Tk()
root.title("Gestor de Produtos - Integração via WebSocket com Auth")

# Input fields
tk.Label(root, text="ID").grid(row=0, column=0, sticky="w", padx=5)
entry_id = tk.Entry(root)
entry_id.grid(row=0, column=1, padx=5, pady=2)

tk.Label(root, text="Nome").grid(row=1, column=0, sticky="w", padx=5)
entry_nome = tk.Entry(root)
entry_nome.grid(row=1, column=1, padx=5, pady=2)

tk.Label(root, text="Preço").grid(row=2, column=0, sticky="w", padx=5)
entry_preco = tk.Entry(root)
entry_preco.grid(row=2, column=1, padx=5, pady=2)

tk.Label(root, text="Stock").grid(row=3, column=0, sticky="w", padx=5)
entry_stock = tk.Entry(root)
entry_stock.grid(row=3, column=1, padx=5, pady=2)

# Authentication button
tk.Button(root, text="🔐 Login", command=authenticate, bg="lightblue").grid(row=4, column=0, columnspan=2, pady=10)

# API buttons
tk.Button(root, text="Criar (REST)", command=criar_produto_rest).grid(row=5, column=0, pady=5)
tk.Button(root, text="Listar (SOAP)", command=listar_produtos_soap).grid(row=5, column=1, pady=5)
tk.Button(root, text="Atualizar (gRPC)", command=atualizar_produto_grpc).grid(row=6, column=0, pady=5)
tk.Button(root, text="Remover (GraphQL)", command=remover_produto_graphql).grid(row=6, column=1, pady=5)

# Status Labels
ws_status_var = tk.StringVar(value="Disconnected")
auth_status_var = tk.StringVar(value="Not Authenticated")
user_info_var = tk.StringVar(value="Not logged in")

tk.Label(root, text="WebSocket:").grid(row=7, column=0, sticky="w", padx=5)
tk.Label(root, textvariable=ws_status_var, fg="blue").grid(row=7, column=1, sticky="w")

tk.Label(root, text="Auth Status:").grid(row=8, column=0, sticky="w", padx=5)
tk.Label(root, textvariable=auth_status_var, fg="green").grid(row=8, column=1, sticky="w")

tk.Label(root, text="User:").grid(row=9, column=0, sticky="w", padx=5)
tk.Label(root, textvariable=user_info_var, fg="purple").grid(row=9, column=1, sticky="w")

# Output
text_output = tk.Text(root, height=15, width=70)
text_output.grid(row=10, column=0, columnspan=2, padx=10, pady=10)

# Help text
help_text = """
Demo Users:
• admin / admin123 (all permissions)
• user / user123 (create, read, update)
• readonly / readonly123 (read only)
"""
tk.Label(root, text=help_text, justify=tk.LEFT, fg="gray").grid(row=11, column=0, columnspan=2, padx=10)

# Start WebSocket client in a separate thread
ws_thread = threading.Thread(target=start_websocket)
ws_thread.daemon = True
ws_thread.start()

root.mainloop()