import os
import logging
import json
import pandas as pd
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from tavily import TavilyClient
from fpdf import FPDF
import google.generativeai as genai

# --- 1. CONFIGURAÇÃO INICIAL ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. CARREGAMENTO DAS CHAVES E CLIENTES ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. DEFINIÇÃO DAS FERRAMENTAS ---
class PDF(FPDF):
    def header(self):
        if hasattr(self, 'title') and self.title: self.set_font("Arial", "B", 12); self.cell(0, 10, self.title, 0, 0, "C"); self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font("Arial", "I", 8); self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")

def tavily_search(query: str) -> dict:
    logger.info(f"Executando busca para: '{query}'")
    try:
        response = tavily_client.search(query=query, search_depth="basic", max_results=5)
        return {"result": "\n\n".join([f"Fonte: {obj['url']}\nConteúdo: {obj['content']}" for obj in response['results']])}
    except Exception as e: return {"error": str(e)}

def gerar_pdf_avancado(titulo_documento: str, estrutura_json: str) -> dict:
    logger.info(f"Gerando PDF: {titulo_documento}")
    try:
        data = json.loads(estrutura_json)
        pdf = PDF(); pdf.set_title(data.get('titulo_geral', 'Documento')); pdf.add_page()
        for secao in data.get('secoes', []):
            pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, secao.get('titulo', '').encode('latin-1', 'replace').decode('latin-1'), 0, 1, "L"); pdf.ln(5)
            pdf.set_font("Arial", "", 12); conteudo = secao.get('conteudo', '').encode('latin-1', 'replace').decode('latin-1'); pdf.multi_cell(0, 10, conteudo); pdf.ln(10)
        pdf.output(titulo_documento)
        return {"file_path": titulo_documento}
    except Exception as e: return {"error": str(e)}

def gerar_planilha_excel(nome_arquivo: str, dados_json: str) -> dict:
    logger.info(f"Gerando planilha: {nome_arquivo}")
    try:
        dados = json.loads(dados_json)
        with pd.ExcelWriter(nome_arquivo, engine='openpyxl') as writer:
            for nome_aba, linhas in dados.items():
                if not linhas: continue
                df = pd.DataFrame(linhas[1:], columns=linhas[0]); df.to_excel(writer, sheet_name=nome_aba, index=False)
        return {"file_path": nome_arquivo}
    except Exception as e: return {"error": str(e)}

# --- 4. CONFIGURAÇÃO DO MODELO DE IA ---
model = None
tools = []
try:
    if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, TAVILY_API_KEY]):
        raise ValueError("Uma ou mais chaves de API estão faltando.")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name="models/gemini-pro-latest",
        system_instruction=(
            "Seu nome é Alfred. Você é um mentor de vida, um conselheiro pragmático e experiente..." # Sua persona
        )
    )
    tools = [tavily_search, gerar_pdf_avancado, gerar_planilha_excel]
    logger.info("Modelo de IA inicializado com sucesso (MODO ROBUSTO).")
except Exception as e:
    logger.critical(f"FALHA CRÍTICA NA INICIALIZAÇÃO DO MODELO: {e}")

# --- 5. LÓGICA PRINCIPAL DO BOT (COM LOOP DE FERRAMENTAS UNIFICADO) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model: await update.message.reply_text("Perdão, Senhor. Falha crítica na configuração inicial."); return
    context.chat_data.clear(); await update.message.reply_text("Olá, Senhor. O que deseja?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model: await update.message.reply_text("Perdão, Senhor. Falha crítica na configuração inicial."); return
    
    user_message = update.message.text
    chat_id = update.effective_chat.id
    if not user_message: return

    await update.message.chat.send_action(action='typing')
    try:
        if 'history' not in context.chat_data: context.chat_data['history'] = []
        history = context.chat_data['history']
        history.append({'role': 'user', 'parts': [user_message]})

        # Loop de execução de ferramentas
        while True:
            response = model.generate_content(history, tools=tools)
            candidate = response.candidates[0]
            
            # Se a resposta NÃO for uma chamada de função, saia do loop
            if not candidate.content.parts or not candidate.content.parts[0].function_call:
                break
            
            # Se for uma chamada de função, execute-a
            function_call = candidate.content.parts[0].function_call
            tool_name = function_call.name
            args = {key: value for key, value in function_call.args.items()}
            logger.info(f"IA solicitou a ferramenta '{tool_name}' com os argumentos: {args}")

            tool_function = {"tavily_search": tavily_search, "gerar_pdf_avancado": gerar_pdf_avancado, "gerar_planilha_excel": gerar_planilha_excel}.get(tool_name)
            
            if not tool_function: raise ValueError(f"Ferramenta desconhecida: {tool_name}")

            function_response = tool_function(**args)
            
            # Adiciona a chamada e o resultado ao histórico para a IA saber o que aconteceu
            history.append({'role': 'model', 'parts': [{'function_call': function_call}]})
            history.append({'role': 'function', 'parts': [{'function_response': {'name': tool_name, 'response': function_response}}]})
            # Fim da iteração do loop, o código voltará para model.generate_content

        # Processa a resposta final da IA (que é texto)
        final_text = response.text
        history.append({'role': 'model', 'parts': [final_text]})
        
        # Verifica se a última ação foi gerar um arquivo para enviar
        last_tool_response = history[-2]['parts'][0]['function_response']['response'] if len(history) > 1 and 'function_response' in history[-2]['parts'][0] else {}
        if 'file_path' in last_tool_response:
            file_path = last_tool_response['file_path']
            await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'))
            os.remove(file_path)
            # Se a IA não gerou um texto de acompanhamento, envie uma confirmação
            if not final_text.strip():
                await update.message.reply_text(f"Senhor, o arquivo '{os.path.basename(file_path)}' foi gerado como solicitado.")
            else:
                await update.message.reply_text(final_text) # Envia o texto que acompanha o arquivo
        elif final_text:
            await update.message.reply_text(final_text)

    except Exception as e:
        logger.error(f"Erro inesperado no handle_message: {e}")
        await update.message.reply_text(f"Contratempo detectado. Detalhe técnico: {e}")

# --- 6. PONTO DE ENTRADA ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Iniciando bot Alfred - Versão Definitiva 2.3 (Arquitetura Robusta).")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
