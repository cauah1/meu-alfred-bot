import os
import logging
import json
import pandas as pd
import requests
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from tavily import TavilyClient
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO INICIAL ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. CARREGAMENTO DAS CHAVES E CLIENTES ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. DEFINIÇÃO DAS FERRAMENTAS (Existem, mas não serão todas ativadas) ---
def tavily_search(query: str) -> str:
    """Ferramenta de busca na internet para obter informações em tempo real ou sobre eventos recentes."""
    logger.info(f"Executando busca para: '{query}'")
    try:
        response = tavily_client.search(query=query, search_depth="basic", max_results=3)
        return "\n".join([f"Fonte: {obj['url']}\nConteúdo: {obj['content']}" for obj in response['results']])
    except Exception as e:
        return f"Erro ao buscar: {e}"

# As funções abaixo existem, mas não serão passadas para a IA por enquanto.
def gerar_pdf_avancado(titulo_documento: str, estrutura_json: str) -> str:
    pass
def gerar_planilha_excel(nome_arquivo: str, dados_json: str) -> str:
    pass

# --- 4. CONFIGURAÇÃO DO MODELO DE IA (MODO DE ESTABILIZAÇÃO) ---
model = None
try:
    if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, TAVILY_API_KEY]):
        raise ValueError("Uma ou mais chaves de API estão faltando.")
        
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name="models/gemini-pro-latest",
        tools=[tavily_search], # APENAS A FERRAMENTA DE BUSCA ESTÁ ATIVA
        system_instruction=(
            "Seu nome é Alfred. Você é um mentor de vida, um conselheiro pragmático e experiente..." # Sua persona completa aqui
        )
    )
    logger.info("Modelo de IA configurado com sucesso em MODO DE ESTABILIZAÇÃO.")
except Exception as e:
    logger.critical(f"Erro crítico ao configurar a IA. O bot não pode funcionar. Erro: {e}")

# --- 5. LÓGICA PRINCIPAL DO BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model:
        await update.message.reply_text("Perdão, Senhor. Estou com uma falha crítica na minha configuração inicial e não posso operar.")
        return
    context.chat_data.clear()
    await update.message.reply_text("Olá, Senhor. O que deseja?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model:
        await update.message.reply_text("Perdão, Senhor. Estou com uma falha crítica na minha configuração inicial e não posso operar.")
        return
        
    user_message = update.message.text
    if not user_message: return

    await update.message.chat.send_action(action='typing')

    try:
        if 'chat' not in context.chat_data:
            context.chat_data['chat'] = model.start_chat(enable_automatic_function_calling=True)
        
        chat = context.chat_data['chat']
        response = chat.send_message(user_message)
        
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Erro no handle_message: {e}")
        await update.message.reply_text(f"Contratempo detectado. Detalhe técnico: {e}")

# --- 6. PONTO DE ENTRADA ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Iniciando bot Alfred...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
