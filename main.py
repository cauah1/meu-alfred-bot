import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuração de logging para ver o que o bot está fazendo
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURAÇÃO DAS CHAVES E DA IA ---
# As chaves foram inseridas diretamente no código para garantir o funcionamento.

TELEGRAM_BOT_TOKEN = "8322649825:AAEfqCNLaIRpwfkFS-MBE_76_66RgBZ36x8"
GOOGLE_API_KEY = "AIzaSyDk_7DkIAuheecGQM2NLXEa14DBUt2jhRw"

try:
    if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
        raise ValueError("Uma das chaves não foi inserida no código.")

    genai.configure(api_key=GOOGLE_API_KEY)

    # Definição da personalidade do Alfred (System Prompt)
    model = genai.GenerativeModel(
        model_name="gemini-pro",
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
except Exception as e:
    logger.critical(f"Erro crítico na inicialização: {e}")
    # Se houver erro aqui, o bot não pode iniciar.

# --- 2. FUNÇÕES DO BOT (O que ele faz) ---

# Função para o comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Olá, Mestre {user.mention_html()}. Eu sou Alfred, à sua disposição. Como posso ser útil hoje?",
    )

# Função para lidar com mensagens de texto usando a IA
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    if not user_message:
        return

    logger.info(f"Mensagem recebida de {update.effective_user.name}: '{user_message}'")
    await update.message.chat.send_action(action='typing') # Mostra "digitando..."

    try:
        # Envia a mensagem para o Gemini e obtém a resposta
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Erro ao interagir com a IA: {e}")
        # Mensagem de erro para o usuário final
        await update.message.reply_text(
            "Perdão, Mestre. Parece que tive um pequeno contratempo. Poderia tentar novamente em alguns instantes?"
        )
        # Mensagem de erro para você, o desenvolvedor, para saber o que aconteceu
        await update.message.reply_text(f"(Erro técnico para o desenvolvedor: {e})")


# --- 3. FUNÇÃO PRINCIPAL (Onde o bot é iniciado) ---
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("Token do Telegram não configurado. O bot não pode iniciar.")
        return

    # Cria o 'aplicativo' do bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Adiciona os 'manipuladores' para comandos e mensagens
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Inicia o bot para ele ficar 'ouvindo'
    logger.info("Iniciando o bot Alfred...")
    application.run_polling()

if __name__ == "__main__":
    main()
