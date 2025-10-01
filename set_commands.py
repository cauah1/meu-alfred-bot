import requests
import json

# ===============================================================
# ATENÇÃO: Insira o seu Token do Telegram aqui dentro das aspas
# ===============================================================
BOT_TOKEN = "8322649825:AAEfqCNLaIRpwfkFS-MBE_76_66RgBZ36x8"


# Definição dos comandos que você quer que apareçam no menu
# Cada comando tem um 'command' (o nome que o usuário digita) e uma 'description'
my_commands = [
    {"command": "start", "description": "Inicia ou reinicia a conversa com o Alfred"},
    {"command": "pdf", "description": "Gera um documento PDF a partir de uma instrução"},
    {"command": "planilha", "description": "Gera uma planilha Excel a partir de uma instrução"}
]

# Converte a lista de comandos para o formato JSON
commands_json = json.dumps(my_commands)

# Monta a URL da API do Telegram para o método setMyCommands
url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"

# Define os parâmetros da requisição
params = {
    "commands": commands_json
}

# Envia a requisição para a API do Telegram
try:
    response = requests.get(url, params=params )
    response.raise_for_status()  # Lança um erro se a requisição falhar
    
    # Verifica a resposta
    result = response.json()
    if result.get("ok"):
        print("Comandos configurados com sucesso no Telegram!")
        print("Pode demorar alguns minutos para o menu atualizar no seu aplicativo.")
    else:
        print("Ocorreu um erro ao configurar os comandos:")
        print(result)

except requests.exceptions.RequestException as e:
    print(f"Erro de conexão ao tentar falar com a API do Telegram: {e}")
except Exception as e:
    print(f"Um erro inesperado ocorreu: {e}")

