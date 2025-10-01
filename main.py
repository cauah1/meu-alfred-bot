import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuração Padrão ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx" ).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Carregamento das Chaves ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
    logger.critical("ERRO CRÍTICO: Uma das variáveis de ambiente não foi encontrada.")

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info("Configuração da API do Google concluída.")
except Exception as e:
    logger.critical(f"Erro crítico ao configurar a API do Google: {e}")

# --- FUNÇÃO DE DIAGNÓSTICO ---

# Nova função para o comando /verificar
async def verificar_modelos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Ok, Mestre. Vou verificar diretamente com o Google quais modelos estão disponíveis para a sua chave. Um momento...")
    logger.info("Executando verificação de modelos...")
    
    try:
        model_list = []
        # Esta função pede ao Google a lista de modelos
        for m in genai.list_models():
            # Verificamos se o modelo suporta o método 'generateContent'
            if 'generateContent' in m.supported_generation_methods:
                model_list.append(m.name)
        
        if model_list:
            # Formata a lista para exibição
            modelos_disponiveis = "\n".join(model_list)
            await update.message.reply_text(f"Verificação concluída. Os modelos que podemos usar são:\n\n{modelos_disponiveis}")
        else:
            await update.message.reply_text("Verificação concluída, mas algo está muito errado. Nenhum modelo compatível foi encontrado.")
            
    except Exception as e:
        logger.error(f"Erro durante a verificação de modelos: {e}")
        await update.message.reply_text(f"Falha ao verificar. O erro técnico retornado foi: {e}")

# --- Funções Antigas (desativadas para o teste) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        f"Olá, Mestre {update.effective_user.mention_html()}. No momento, estou em modo de diagnóstico. Por favor, envie o comando /verificar para prosseguir.",
    )

# --- Ponto de Entrada ---
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("Bot não pode iniciar sem token.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Adicionando o novo comando de verificação
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("verificar", verificar_modelos))

    logger.info("Iniciando bot em MODO DE DIAGNÓSTICO...")
    application.run_polling()

if __name__ == "__main__":
    main()
