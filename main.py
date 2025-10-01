import os
import logging
import json
import pandas as pd
import re
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fpdf import FPDF
import google.generativeai as genai

# --- 1. CONFIGURAÇÃO INICIAL ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. CARREGAMENTO DAS CHAVES E CLIENTES ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- 3. FUNÇÕES AUXILIARES E DE GERAÇÃO ---

def extrair_json(texto: str) -> str:
    """Extrai um bloco de código JSON de uma string de texto, mesmo que haja outro texto ao redor."""
    # Procura por blocos de código JSON marcados com ```json ... ``` ou apenas o JSON bruto
    match = re.search(r'```json\s*(\{.*?\})\s*```', texto, re.DOTALL)
    if match:
        return match.group(1)
    # Se não encontrar o bloco marcado, tenta encontrar qualquer JSON válido na string
    match = re.search(r'(\{.*?\})', texto, re.DOTALL)
    if match:
        return match.group(1)
    return texto # Retorna o texto original se nada for encontrado

class PDF(FPDF):
    def header(self):
        if hasattr(self, 'title') and self.title: self.set_font("Arial", "B", 12); self.cell(0, 10, self.title, 0, 0, "C"); self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font("Arial", "I", 8); self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")

def criar_arquivo_pdf(titulo_documento: str, instrucao_ia: str) -> str:
    logger.info(f"Gerando PDF para: {instrucao_ia}")
    try:
        prompt = f"Crie o conteúdo para um documento PDF com base na seguinte instrução: '{instrucao_ia}'. Responda APENAS com uma estrutura JSON contendo uma chave 'secoes', que é uma lista de dicionários, cada um com 'titulo' e 'conteudo'."
        response = model.generate_content(prompt)
        json_text = extrair_json(response.text) # <-- USA A FUNÇÃO DE EXTRAÇÃO
        data = json.loads(json_text)
        
        pdf = PDF(); pdf.set_title(titulo_documento); pdf.add_page()
        for secao in data.get('secoes', []):
            pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, secao.get('titulo', '').encode('latin-1', 'replace').decode('latin-1'), 0, 1, "L"); pdf.ln(5)
            pdf.set_font("Arial", "", 12); conteudo = secao.get('conteudo', '').encode('latin-1', 'replace').decode('latin-1'); pdf.multi_cell(0, 10, conteudo); pdf.ln(10)
        
        file_path = f"{titulo_documento.replace(' ', '_')}.pdf"
        pdf.output(file_path)
        return file_path
    except Exception as e:
        logger.error(f"Erro ao criar PDF: {e}")
        return f"Erro: {e}"

def criar_arquivo_planilha(nome_arquivo: str, instrucao_ia: str) -> str:
    logger.info(f"Gerando Planilha para: {instrucao_ia}")
    try:
        prompt = f"Crie os dados para uma planilha com base na seguinte instrução: '{instrucao_ia}'. Responda APENAS com uma estrutura JSON. O JSON deve ser um dicionário onde cada chave é o nome de uma aba e o valor é uma lista de listas, com a primeira lista sendo o cabeçalho."
        response = model.generate_content(prompt)
        json_text = extrair_json(response.text) # <-- USA A FUNÇÃO DE EXTRAÇÃO
        dados = json.loads(json_text)

        with pd.ExcelWriter(nome_arquivo, engine='openpyxl') as writer:
            for nome_aba, linhas in dados.items():
                if not linhas: continue
                df = pd.DataFrame(linhas[1:], columns=linhas[0]); df.to_excel(writer, sheet_name=nome_aba, index=False)
        return nome_arquivo
    except Exception as e:
        logger.error(f"Erro ao criar Planilha: {e}")
        return f"Erro: {e}"

# --- 4. CONFIGURAÇÃO DO MODELO DE IA ---
model = None
try:
    if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY]):
        raise ValueError("Chaves de API faltando.")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name="models/gemini-pro-latest",
        system_instruction=(
            "Seu nome é Alfred. Você é um mentor de vida, um conselheiro pragmático e experiente..." # Sua persona
        )
    )
    logger.info("Modelo de IA inicializado com sucesso (MODO ESTÁVEL).")
except Exception as e:
    logger.critical(f"FALHA CRÍTICA NA INICIALIZAÇÃO DO MODELO: {e}")

# --- 5. LÓGICA DOS COMANDOS DO BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model: await update.message.reply_text("Perdão, Senhor. Falha crítica na configuração inicial."); return
    context.chat_data.clear()
    await update.message.reply_text("Olá, Senhor. O que deseja? Para gerar arquivos, use os comandos /pdf ou /planilha.")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model: await update.message.reply_text("Perdão, Senhor. Falha crítica na configuração inicial."); return
    user_message = update.message.text
    if not user_message: return
    await update.message.chat.send_action(action='typing')
    try:
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"Contratempo na conversa. Detalhe: {e}")

async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model: await update.message.reply_text("Perdão, Senhor. Falha crítica na configuração inicial."); return
    instrucao = " ".join(context.args)
    if not instrucao:
        await update.message.reply_text("Uso do comando: /pdf <instrução para o conteúdo do PDF>")
        return
    
    await update.message.reply_text("Entendido. Preparando o documento PDF...")
    await update.message.chat.send_action(action='upload_document')
    
    file_path = criar_arquivo_pdf("documento", instrucao)
    
    if "Erro:" not in file_path:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
        os.remove(file_path)
    else:
        await update.message.reply_text(f"Falha ao gerar o PDF. Detalhe técnico: {file_path}")

async def planilha_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model: await update.message.reply_text("Perdão, Senhor. Falha crítica na configuração inicial."); return
    instrucao = " ".join(context.args)
    if not instrucao:
        await update.message.reply_text("Uso do comando: /planilha <instrução para os dados da planilha>")
        return

    await update.message.reply_text("Entendido. Compilando os dados para a planilha...")
    await update.message.chat.send_action(action='upload_document')

    file_path = criar_arquivo_planilha("planilha.xlsx", instrucao)

    if "Erro:" not in file_path:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
        os.remove(file_path)
    else:
        await update.message.reply_text(f"Falha ao gerar a planilha. Detalhe técnico: {file_path}")

# --- 6. PONTO DE ENTRADA ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pdf", pdf_command))
    application.add_handler(CommandHandler("planilha", planilha_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))
    
    logger.info("Iniciando bot Alfred - Versão 3.1 (com extração de JSON).")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
