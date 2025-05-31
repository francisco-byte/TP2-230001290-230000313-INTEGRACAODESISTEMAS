import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import threading
import websocket
import time

# Variáveis globais para gerir a ligação WebSocket e autenticação
ws_connection = None
is_authenticated = False
user_permissions = []
current_user = None

def get_input():
    """Recolhe e valida os dados de entrada do formulário"""
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
    """Gere a autenticação OAuth2 com o servidor"""
    if not ws_connection:
        mostrar_resposta({"error": "WebSocket not connected"})
        return
    
    # Solicita credenciais do utilizador através de diálogos
    username = simpledialog.askstring("OAuth2 Login", "Username:")
    password = simpledialog.askstring("OAuth2 Login", "Password:", show='*')
    
    if username and password:
        # Prepara pedido OAuth2 Resource Owner Password Credentials Grant
        oauth2_request = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": "read_product create_product update_product delete_product"
        }
        ws_connection.send(json.dumps(oauth2_request))

def send_ws_request(action, data=None):
    """Envia pedidos através da ligação WebSocket"""
    if not ws_connection:
        mostrar_resposta({"erro": "WebSocket not connected"})
        return
        
    if not is_authenticated:
        mostrar_resposta({"erro": "Please authenticate first"})
        return
    
    # Constrói mensagem padronizada para envio
    message = {
        "action": action,
        "data": data or {}
    }
    try:
        ws_connection.send(json.dumps(message))
    except Exception as e:
        mostrar_resposta({"erro": f"WebSocket send error: {str(e)}"})

def criar_produto_rest():
    """Cria produto usando API REST"""
    try:
        produto = get_input()
        send_ws_request("create_rest", produto)
    except ValueError as e:
        mostrar_resposta({"error": str(e)})

def listar_produtos_soap():
    """Lista produtos usando API SOAP"""
    send_ws_request("list_soap")

def atualizar_produto_grpc():
    """Actualiza produto usando API gRPC"""
    try:
        produto = get_input()
        send_ws_request("update_grpc", produto)
    except ValueError as e:
        mostrar_resposta({"error": str(e)})

def remover_produto_graphql():
    """Remove produto usando API GraphQL"""
    try:
        id_produto = int(entry_id.get())
        send_ws_request("delete_graphql", {"id": id_produto})
    except ValueError:
        mostrar_resposta({"error": "ID must be a number"})

def mostrar_resposta(data):
    """Actualiza a área de saída com a resposta recebida de forma thread-safe"""
    if root:
        root.after(0, lambda d=data: (
            text_output.delete(1.0, tk.END),
            text_output.insert(tk.END, json.dumps(d, indent=2))
        ))

def update_ws_status(status):
    """Actualiza o estado da ligação WebSocket na interface"""
    if root:
        root.after(0, lambda s=status: ws_status_var.set(s))

def update_auth_status(status):
    """Actualiza o estado de autenticação na interface"""
    if root:
        root.after(0, lambda s=status: auth_status_var.set(s))

def update_user_info(user_info):
    """Actualiza as informações do utilizador na interface"""
    if root:
        root.after(0, lambda info=user_info: user_info_var.set(info))

def on_message(ws, message):
    """Processa mensagens recebidas através do WebSocket"""
    global is_authenticated, user_permissions, current_user
    
    try:
        data = json.loads(message)
        
        # Processa resposta de token OAuth2
        if "access_token" in data and "token_type" in data:
            # Autenticação OAuth2 bem-sucedida
            is_authenticated = True
            current_user = data.get("user_id", "Unknown")
            scope = data.get("scope", "")
            user_permissions = scope.split() if scope else []
            
            update_auth_status("OAuth2 Authenticated")
            update_user_info(f"User: {current_user}")
            mostrar_resposta({
                "oauth2_authentication": "Success",
                "user_id": current_user,
                "email": data.get("email", ""),
                "scope": scope,
                "permissions": user_permissions,
                "token_type": data.get("token_type"),
                "expires_in": f"{data.get('expires_in', 0)} seconds"
            })
            
        # Processa erros de permissão/âmbito OAuth2 (para TODOS os serviços)
        elif "error" in data and data.get("error") == "insufficient_scope":
            # Permissão negada mas utilizador continua autenticado
            action = "Unknown"
            if "required_scope" in data:
                scope_to_action = {
                    "create_product": "Create Product (REST)",
                    "read_product": "List Products (SOAP)",
                    "update_product": "Update Product (gRPC)",
                    "delete_product": "Delete Product (GraphQL)"
                }
                action = scope_to_action.get(data["required_scope"], data["required_scope"])
            
            mostrar_resposta({
                "permission_error": "Access Denied",
                "action_attempted": action,
                "error": data.get("error"),
                "description": data.get("error_description", ""),
                "required_scope": data.get("required_scope", ""),
                "your_permissions": user_permissions,
                "user_id": current_user,
                "message": f"User '{current_user}' doesn't have required permission",
                "suggestion": "Try logging in with 'admin' account for full access"
            })
            
        # Processa OUTROS erros OAuth2 (falhas de autenticação)
        elif "error" in data and "error_description" in data:
            error_code = data.get("error")
            # Apenas reinicia autenticação para erros de autenticação reais
            if error_code in ["invalid_grant", "invalid_token", "access_denied", "invalid_request"]:
                is_authenticated = False
                update_auth_status("OAuth2 Error")
                update_user_info("Authentication failed")
                mostrar_resposta({
                    "oauth2_error": error_code,
                    "description": data.get("error_description")
                })
            else:
                # Outros erros (como server_error) não reiniciam a autenticação
                mostrar_resposta({
                    "api_error": error_code,
                    "description": data.get("error_description")
                })
            
        # Processa resposta de autenticação legada (compatibilidade)
        elif data.get("action") == "auth":
            if data.get("success"):
                is_authenticated = True
                current_user = data.get("message", "").replace("Authenticated as ", "")
                user_permissions = data.get("permissions", [])
                
                update_auth_status("Authenticated")
                update_user_info(f"User: {current_user}")
                mostrar_resposta({
                    "legacy_authentication": "Success",
                    "user": current_user,
                    "permissions": user_permissions
                })
            else:
                is_authenticated = False
                update_auth_status("Failed")
                update_user_info("Not logged in")
                mostrar_resposta({"legacy_authentication": "Failed", "message": data.get("message")})
                
        # Processa respostas de sucesso da API
        elif "action" in data:
            mostrar_resposta(data)
            
        # Processa estado da ligação
        elif "status" in data:
            mostrar_resposta({"connection_status": data})
            
        else:
            # Outras mensagens (notificações, etc.)
            mostrar_resposta({"websocket_update": data})
            
    except json.JSONDecodeError:
        mostrar_resposta({"websocket_message": message})
    except Exception as e:
        mostrar_resposta({"error": f"Message parse error: {str(e)}"})

def on_error(ws, error):
    """Gere erros da ligação WebSocket"""
    mostrar_resposta({"websocket_error": str(error)})
    update_ws_status("Error")

def on_close(ws, close_status_code, close_msg):
    """Gere o fecho da ligação WebSocket e reinicia variáveis de estado"""
    global is_authenticated, user_permissions, current_user
    
    # Reinicia estado de autenticação
    is_authenticated = False
    user_permissions = []
    current_user = None
    
    mostrar_resposta({"websocket_closed": f"Code: {close_status_code}, Message: {close_msg}"})
    update_ws_status("Closed")
    update_auth_status("Not Authenticated")
    update_user_info("Not logged in")
    
    # Tenta reconectar após 5 segundos
    threading.Timer(5.0, start_websocket).start()

def on_open(ws):
    """Gere a abertura da ligação WebSocket"""
    global ws_connection
    ws_connection = ws
    mostrar_resposta({"websocket": "Connection opened"})
    update_ws_status("Connected")

def start_websocket():
    """Inicia a ligação WebSocket com o servidor"""
    global ws_connection
    try:
        ws = websocket.WebSocketApp("ws://192.168.246.46:6789/",
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        ws.on_open = on_open
        ws.run_forever()
    except Exception as e:
        update_ws_status(f"Connection failed: {str(e)}")
        # Tenta reconectar após 5 segundos
        threading.Timer(5.0, start_websocket).start()

# ----------------- Interface Gráfica -----------------
root = tk.Tk()
root.title("Gestor de Produtos - Integração via WebSocket com Auth")

# Campos de entrada de dados
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

# Botão de autenticação
tk.Button(root, text="Login", command=authenticate, bg="lightblue").grid(row=4, column=0, columnspan=2, pady=10)

# Botões das operações API
tk.Button(root, text="Criar (REST)", command=criar_produto_rest).grid(row=5, column=0, pady=5)
tk.Button(root, text="Listar (SOAP)", command=listar_produtos_soap).grid(row=5, column=1, pady=5)
tk.Button(root, text="Atualizar (gRPC)", command=atualizar_produto_grpc).grid(row=6, column=0, pady=5)
tk.Button(root, text="Remover (GraphQL)", command=remover_produto_graphql).grid(row=6, column=1, pady=5)

# Variáveis para etiquetas de estado
ws_status_var = tk.StringVar(value="Disconnected")
auth_status_var = tk.StringVar(value="Not Authenticated")
user_info_var = tk.StringVar(value="Not logged in")

# Etiquetas de estado da ligação e autenticação
tk.Label(root, text="WebSocket:").grid(row=7, column=0, sticky="w", padx=5)
tk.Label(root, textvariable=ws_status_var, fg="blue").grid(row=7, column=1, sticky="w")

tk.Label(root, text="Auth Status:").grid(row=8, column=0, sticky="w", padx=5)
tk.Label(root, textvariable=auth_status_var, fg="green").grid(row=8, column=1, sticky="w")

tk.Label(root, text="User:").grid(row=9, column=0, sticky="w", padx=5)
tk.Label(root, textvariable=user_info_var, fg="purple").grid(row=9, column=1, sticky="w")

# Área de saída para respostas
text_output = tk.Text(root, height=15, width=70)
text_output.grid(row=10, column=0, columnspan=2, padx=10, pady=10)

# Texto de ajuda com utilizadores de demonstração
help_text = """
Demo Users:
• admin / admin123 (all permissions)
• user / user123 (create, read, update)
• readonly / readonly123 (read only)
"""
tk.Label(root, text=help_text, justify=tk.LEFT, fg="gray").grid(row=11, column=0, columnspan=2, padx=10)

# Inicia cliente WebSocket numa thread separada
ws_thread = threading.Thread(target=start_websocket)
ws_thread.daemon = True
ws_thread.start()

# Inicia o loop principal da interface gráfica
root.mainloop()