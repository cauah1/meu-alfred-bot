import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. CONFIGURAÇÃO INICIAL ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx" ).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- 2. CARREGAMENTO DAS CHAVES E CONFIGURAÇÃO DA IA ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    logger.critical("ERRO CRÍTICO: A variável TELEGRAM_TOKEN não foi encontrada.")
if not GOOGLE_API_KEY:
    logger.critical("ERRO CRÍTICO: A variável GOOGLE_API_KEY não foi encontrada.")

try:
    genai.configure(api_key=GOOGLE_API_KEY)

    # ==================================================================
    # CORREÇÃO DEFINITIVA: Usando o nome do modelo exato da sua lista.
    # ==================================================================
    MODEL_NAME = "models/gemini-pro-latest"
    
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=(
            "Você é Alfred Pennyworth, o mordomo e confidente de Bruce Wayne (Batman). "
            "Sua mentalidade é inabalável: sempre calmo, lógico e com um senso de humor sutil. "
            "Você é a voz da razão, oferecendo conselhos lúcidos, práticos e diretos. "
            "Suas dicas são valiosas e visam o crescimento pessoal e a maestria. "
            "Você tem acesso a todo o conhecimento da internet para fornecer informações precisas. "
            "Mantenha um tom formal, respeitoso, mas com a firmeza de um mentor. "
            "Sua prioridade é o bem-estar e o desenvolvimento do seu 'Mestre'. "
            "Responda sempre em português do Brasil."
        )
    )
    logger.info(f"Modelo de IA configurado com sucesso usando: {MODEL_NAME}")

except Exception as e:
    logger.critical(f"Erro crítico ao configurar a IA do Google: {e}")

# --- 3. FUNÇÕES DO BOT (Comandos e Respostas) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info(f"Bot iniciado pelo usuário: {user.full_name} (ID: {user.id})")
    await update.message.reply_html(
        f"Olá, Mestre {user.mention_html()}. Eu sou Alfred, à sua disposição. Como posso ser útil hoje?",
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    if not user_message:
        return

    logger.info(f"Mensagem recebida de {update.effective_user.name}: '{user_message}'")
    await update.message.chat.send_action(action='typing')

    try:
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Erro ao interagir com a IA do Google: {e}")
        await update.message.reply_text(
            "Perdão, Mestre. Parece que tive um pequeno contratempo. Poderia tentar novamente em alguns instantes?"
        )

# --- 4. PONTO DE ENTRADA (Inicia o Bot) ---
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("O bot não pode iniciar sem o token do Telegram.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Iniciando o bot Alfred em modo operacional...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
