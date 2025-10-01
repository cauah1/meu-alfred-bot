import os
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from collections import deque
from tavily import TavilyClient

# --- 1. CONFIGURAÇÃO INICIAL ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx" ).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- 2. CARREGAMENTO DAS CHAVES E CONFIGURAÇÃO DAS FERRAMENTAS ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") # Nova chave para a busca

if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, TAVILY_API_KEY]):
    logger.critical("ERRO CRÍTICO: Uma ou mais variáveis de ambiente não foram encontradas.")

# Configura o cliente da ferramenta de busca
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. DEFINIÇÃO DA FERRAMENTA DE BUSCA ---
# Esta é a função que o Gemini aprenderá a usar.
def tavily_search(query: str) -> str:
    """
    Uma ferramenta de busca na internet para obter informações em tempo real ou sobre eventos recentes.
    Use-a para responder perguntas sobre notícias, cotações, resultados esportivos, etc.
    Argumentos:
        query (str): A pergunta ou tópico a ser pesquisado.
    """
    logger.info(f"Executando ferramenta de busca para a query: '{query}'")
    try:
        response = tavily_client.search(query=query, search_depth="basic")
        # Retorna um resumo conciso dos resultados
        return "\n".join([f"Fonte: {obj['url']}\nConteúdo: {obj['content']}" for obj in response['results']])
    except Exception as e:
        logger.error(f"Erro na ferramenta de busca Tavily: {e}")
        return f"Erro ao tentar buscar informações: {e}"

# --- 4. CONFIGURAÇÃO DO MODELO DE IA COM FERRAMENTAS ---
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    MODEL_NAME = "models/gemini-pro-latest"
    
    # Informa ao Gemini sobre a ferramenta que ele pode usar
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        tools=[tavily_search], # <-- AQUI informamos a ferramenta
        system_instruction=(
            # ... (Sua instrução de sistema do sargento vai aqui) ...
            "Você é 'Alfred', uma figura paterna e mentor..."
        )
    )
    logger.info(f"Modelo de IA configurado com sucesso usando: {MODEL_NAME} e a ferramenta de busca.")

except Exception as e:
    logger.critical(f"Erro crítico ao configurar a IA do Google: {e}")

# --- 5. FUNÇÕES DO BOT (Lógica Principal) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data.clear()
    logger.info(f"Bot iniciado pelo usuário: {update.effective_user.full_name}")
    await update.message.reply_text("Olá, Senhor. O que deseja?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    if not user_message:
        return

    logger.info(f"Mensagem recebida: '{user_message}'")
    await update.message.chat.send_action(action='typing')

    try:
        # Inicia a sessão de chat com memória
        if 'chat' not in context.chat_data:
            context.chat_data['chat'] = model.start_chat(enable_automatic_function_calling=True)
        
        chat = context.chat_data['chat']
        
        # Envia a mensagem do usuário para o Gemini.
        # O Gemini pode responder com texto ou com um pedido para usar uma ferramenta.
        response = chat.send_message(user_message)
        
        # O texto final da resposta da IA
        final_response = response.text
        
        await update.message.reply_text(final_response)

    except Exception as e:
        logger.error(f"Erro no handle_message: {e}")
        await update.message.reply_text("Perdão, Senhor. Tive um contratempo. Por favor, repita a ordem.")

# --- 6. PONTO DE ENTRADA ---
def main() -> None:
    # ... (código do main continua o mesmo) ...
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Iniciando o bot Alfred em modo operacional (com memória e ferramentas)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
