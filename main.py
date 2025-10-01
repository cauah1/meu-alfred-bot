import os
import logging
import json
import pandas as pd
import requests
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
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

# --- 3. DEFINIÇÃO DAS FERRAMENTAS AVANÇADAS ---
class PDF(FPDF):
    def header(self):
        if hasattr(self, 'title') and self.title:
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, self.title, 0, 0, "C")
            self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")

def gerar_pdf_avancado(titulo_documento: str, estrutura_json: str) -> str:
    logger.info(f"Gerando PDF avançado: {titulo_documento}")
    try:
        data = json.loads(estrutura_json)
        pdf = PDF()
        pdf.set_title(data.get('titulo_geral', 'Relatório'))
        pdf.add_page()
        for secao in data.get('secoes', []):
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, secao.get('titulo', ''), 0, 1, "L")
            pdf.ln(5)
            pdf.set_font("Arial", "", 12)
            conteudo = secao.get('conteudo', '').encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 10, conteudo)
            pdf.ln(10)
        pdf.output(titulo_documento)
        return titulo_documento
    except Exception as e:
        logger.error(f"Erro na geração de PDF avançado: {e}")
        return f"Erro ao gerar PDF: {e}"

def gerar_planilha_excel(nome_arquivo: str, dados_json: str) -> str:
    logger.info(f"Gerando planilha Excel: {nome_arquivo}")
    try:
        dados = json.loads(dados_json)
        with pd.ExcelWriter(nome_arquivo, engine='openpyxl') as writer:
            for nome_aba, linhas in dados.items():
                if not linhas: continue
                df = pd.DataFrame(linhas)
                if not df.empty:
                    df.columns = df.iloc[0]
                    df = df[1:]
                df.to_excel(writer, sheet_name=nome_aba, index=False)
        return nome_arquivo
    except Exception as e:
        logger.error(f"Erro na geração de planilha: {e}")
        return f"Erro ao gerar planilha: {e}"

# --- 4. CONFIGURAÇÃO DO MODELO DE IA ---
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name="models/gemini-pro-latest",
        tools=[tavily_search, gerar_pdf_avancado, gerar_planilha_excel],
        system_instruction=(
            "Seu nome é Alfred. Você é um mentor de vida, um conselheiro pragmático e experiente..." # Sua persona completa aqui
        )
    )
    logger.info("Modelo de IA configurado com todas as ferramentas.")
except Exception as e:
    logger.critical(f"Erro crítico ao configurar a IA: {e}")

# --- 5. LÓGICA PRINCIPAL DO BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data.clear()
    await update.message.reply_text("Olá, Senhor. O que deseja?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    chat_id = update.effective_chat.id
    if not user_message: return

    await update.message.chat.send_action(action='typing')

    try:
        if 'chat' not in context.chat_data:
            context.chat_data['chat'] = model.start_chat(enable_automatic_function_calling=True)
        
        chat = context.chat_data['chat']
        response = chat.send_message(user_message)
        
        if response.function_calls:
            # Esta parte foi removida para simplificar o diagnóstico.
            # O código original estava correto, mas queremos ver o erro bruto primeiro.
            pass

        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Erro no handle_message: {e}")
        # Linha de diagnóstico para nos mostrar o erro exato no Telegram
        await update.message.reply_text(f"Contratempo detectado. Detalhe técnico: {e}")

# --- 6. PONTO DE ENTRADA ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Iniciando bot Alfred em MODO DE DIAGNÓSTICO...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
