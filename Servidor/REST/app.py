from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# Caminho absoluto para o arquivo 'produtos.json' na pasta 'shared'
SHARED_DIR = '/shared'  # Diretório compartilhado mapeado no contêiner
DATA_FILE = os.path.join(SHARED_DIR, 'produtos.json')

def carregar_dados():
    """Carrega os dados do arquivo 'produtos.json'."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def salvar_dados(dados):
    """Salva os dados no arquivo 'produtos.json'."""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(dados, f, indent=2)
    except Exception as e:
        print(f"Erro ao salvar dados: {e}")

@app.route('/create', methods=['POST'])
def create_produto():
    """Cria um novo produto no arquivo 'produtos.json'."""
    try:
        produto = request.json
        produtos = carregar_dados()

        # Evita produtos com o mesmo ID
        if any(p['id'] == produto['id'] for p in produtos):
            return jsonify({'erro': 'ID já existente'}), 400

        produtos.append(produto)
        salvar_dados(produtos)
        return jsonify({'mensagem': f"Produto {produto['name']} criado com sucesso!"})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
