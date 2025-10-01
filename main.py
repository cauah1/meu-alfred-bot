import os
import logging
import google.generativeai as genai
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from tavily import TavilyClient
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO INICIAL ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx" ).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- 2. CARREGAMENTO DAS CHAVES E CONFIGURAÇÃO DOS CLIENTES ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, TAVILY_API_KEY]):
    logger.critical("ERRO CRÍTICO: Uma ou mais variáveis de ambiente não foram encontradas.")

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. DEFINIÇÃO DAS FERRAMENTAS ---

def tavily_search(query: str) -> str:
    """Ferramenta de busca na internet para obter informações em tempo real ou sobre eventos recentes."""
    logger.info(f"Executando ferramenta de busca para a query: '{query}'")
    try:
        response = tavily_client.search(query=query, search_depth="basic", max_results=5)
        return "\n\n".join([f"Fonte: {obj['url']}\nConteúdo: {obj['content']}" for obj in response['results']])
    except Exception as e:
        return f"Erro ao buscar: {e}"

# NOVA FERRAMENTA: GERADOR DE PDF
def gerar_pdf(titulo: str, conteudo: str) -> str:
    """
    Cria um arquivo PDF com um título e um corpo de texto.
    Use esta ferramenta quando o usuário pedir para compilar informações em um relatório, documento ou PDF.
    Argumentos:
        titulo (str): O título do documento.
        conteudo (str): O texto principal que será escrito no PDF.
    """
    logger.info(f"Executando ferramenta de geração de PDF com o título: '{titulo}'")
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, titulo, 0, 1, "C")
        pdf.ln(10)
        pdf.set_font("Arial", "", 12)
        # Trata o texto para que a biblioteca aceite caracteres especiais (UTF-8)
        conteudo_tratado = conteudo.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 10, conteudo_tratado)
        
        file_path = f"{titulo.replace(' ', '_')}.pdf"
        pdf.output(file_path)
        logger.info(f"PDF gerado com sucesso em: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Erro na ferramenta de geração de PDF: {e}")
        return f"Erro ao gerar PDF: {e}"

# --- 4. CONFIGURAÇÃO DO MODELO DE IA COM AS FERRAMENTAS ---
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    MODEL_NAME = "models/gemini-pro-latest"
    
    # Adicionamos a nova ferramenta à lista
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        tools=[tavily_search, gerar_pdf], # <-- AMBAS as ferramentas estão aqui
        system_instruction=(
            # ... (Sua instrução de sistema do Mentor Pragmático vai aqui) ...
            "Seu nome é Alfred. Você é um mentor de vida, um conselheiro pragmático e experiente..."
        )
    )
    logger.info(f"Modelo de IA configurado com sucesso com as ferramentas de busca e PDF.")

except Exception as e:
    logger.critical(f"Erro crítico ao configurar a IA do Google: {e}")

# --- 5. FUNÇÕES DO BOT (Lógica Principal) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data.clear()
    await update.message.reply_text("Olá, Senhor. O que deseja?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    chat_id = update.effective_chat.id
    if not user_message:
        return

    await update.message.chat.send_action(action='typing')

    try:
        if 'chat' not in context.chat_data:
            context.chat_data['chat'] = model.start_chat(enable_automatic_function_calling=True)
        
        chat = context.chat_data['chat']
        response = chat.send_message(user_message)
        
        # Verifica se a IA pediu para usar uma ferramenta
        if response.function_calls:
            for function_call in response.function_calls:
                # Se a ferramenta for o gerador de PDF
                if function_call.name == "gerar_pdf":
                    args = function_call.args
                    file_path = gerar_pdf(titulo=args['titulo'], conteudo=args['conteudo'])
                    
                    # Envia o arquivo PDF para o usuário
                    await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'))
                    # Limpa o arquivo gerado do servidor
                    os.remove(file_path)
                    return # Encerra o processamento aqui

        # Se não usou ferramenta ou se a ferramenta era a de busca (que é tratada automaticamente), envia a resposta de texto
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Erro no handle_message: {e}")
        await update.message.reply_text("Perdão, Senhor. Tive um contratempo. Por favor, repita a ordem.")

# --- 6. PONTO DE ENTRADA ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Iniciando o bot Alfred (com memória, busca e gerador de PDF)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
