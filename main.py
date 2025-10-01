import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. CONFIGURAÇÃO INICIAL ---

# Configura o sistema de logging para podermos ver informações e erros no console do Railway.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# Reduz a quantidade de logs de bibliotecas externas para manter o console limpo.
logging.getLogger("httpx" ).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- 2. CARREGAMENTO DAS CHAVES E CONFIGURAÇÃO DA IA ---

# Carrega as chaves de API de forma segura a partir das "Variables" do Railway.
# Este é o método recomendado para proteger suas informações.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Verifica se as chaves foram carregadas corretamente.
if not TELEGRAM_BOT_TOKEN:
    logger.critical("ERRO CRÍTICO: A variável TELEGRAM_TOKEN não foi encontrada.")
if not GOOGLE_API_KEY:
    logger.critical("ERRO CRÍTICO: A variável GOOGLE_API_KEY não foi encontrada.")

try:
    # Configura a API do Google Gemini com a chave.
    genai.configure(api_key=GOOGLE_API_KEY)

    # Define a personalidade do Alfred e o modelo a ser usado.
    # CORREÇÃO: Usando "gemini-1.0-pro", o modelo estável e correto.
    model = genai.GenerativeModel(
        model_name="gemini-1.0-pro",
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
    logger.info("Modelo de IA configurado com sucesso.")

except Exception as e:
    logger.critical(f"Erro crítico ao configurar a IA do Google: {e}")
    # Se a configuração da IA falhar, o bot não poderá funcionar.

# --- 3. FUNÇÕES DO BOT (Comandos e Respostas) ---

# Esta função é chamada quando o usuário envia o comando /start.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info(f"Bot iniciado pelo usuário: {user.full_name} (ID: {user.id})")
    await update.message.reply_html(
        f"Olá, Mestre {user.mention_html()}. Eu sou Alfred, à sua disposição. Como posso ser útil hoje?",
    )

# Esta função lida com qualquer mensagem de texto que não seja um comando.
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    if not user_message:
        return

    logger.info(f"Mensagem recebida de {update.effective_user.name}: '{user_message}'")
    
    # Mostra "digitando..." no chat para o usuário saber que o bot está processando.
    await update.message.chat.send_action(action='typing')

    try:
        # Envia a mensagem do usuário para o modelo Gemini e aguarda a resposta.
        response = model.generate_content(user_message)
        # Envia a resposta da IA de volta para o usuário no Telegram.
        await update.message.reply_text(response.text)
    except Exception as e:
        # Se ocorrer um erro na comunicação com a IA, registra o erro detalhado para você...
        logger.error(f"Erro ao interagir com a IA do Google: {e}")
        # ...e envia uma mensagem de desculpas polida para o usuário.
        await update.message.reply_text(
            "Perdão, Mestre. Parece que tive um pequeno contratempo. Poderia tentar novamente em alguns instantes?"
        )

# --- 4. PONTO DE ENTRADA (Inicia o Bot) ---

def main() -> None:
    """Função principal que monta e inicia o bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("O bot não pode iniciar sem o token do Telegram.")
        return

    # Cria o 'aplicativo' do bot, que gerencia tudo.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Registra os "manipuladores" (handlers).
    # CommandHandler responde a comandos (ex: /start).
    application.add_handler(CommandHandler("start", start))
    # MessageHandler responde a mensagens de texto que não são comandos.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Inicia o bot. Ele começará a "ouvir" por novas mensagens no Telegram.
    logger.info("Iniciando o bot Alfred...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
