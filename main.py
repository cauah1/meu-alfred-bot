import os
import logging
import json
import pandas as pd
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

# --- 3. DEFINIÇÃO DAS FERRAMENTAS (VERSÃO ROBUSTA) ---

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

def tavily_search(query: str) -> str:
    """Busca informações em tempo real na internet sobre um tópico ou pergunta.
    Args:
        query (str): O tópico a ser pesquisado.
    Returns:
        str: Um resumo dos resultados da busca.
    """
    logger.info(f"Executando busca para: '{query}'")
    try:
        response = tavily_client.search(query=query, search_depth="basic", max_results=5)
        return "\n\n".join([f"Fonte: {obj['url']}\nConteúdo: {obj['content']}" for obj in response['results']])
    except Exception as e:
        return f"Erro ao buscar: {e}"

def gerar_pdf_avancado(titulo_documento: str, estrutura_json: str) -> str:
    """Cria um arquivo PDF a partir de uma estrutura JSON. Use para relatórios e documentos.
    Args:
        titulo_documento (str): O nome do arquivo a ser gerado (ex: 'Relatorio.pdf').
        estrutura_json (str): Uma string no formato JSON. O JSON deve conter uma chave 'secoes', que é uma lista de dicionários. Cada dicionário representa uma seção e deve ter as chaves 'titulo' (string) e 'conteudo' (string).
    Returns:
        str: O caminho do arquivo gerado ou uma mensagem de erro.
    """
    logger.info(f"Gerando PDF avançado: {titulo_documento}")
    try:
        data = json.loads(estrutura_json)
        pdf = PDF()
        pdf.set_title(data.get('titulo_geral', 'Documento'))
        pdf.add_page()
        for secao in data.get('secoes', []):
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, secao.get('titulo', '').encode('latin-1', 'replace').decode('latin-1'), 0, 1, "L")
            pdf.ln(5)
            pdf.set_font("Arial", "", 12)
            conteudo = secao.get('conteudo', '').encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 10, conteudo)
            pdf.ln(10)
        pdf.output(titulo_documento)
        return titulo_documento
    except Exception as e:
        return f"Erro ao gerar PDF: {e}"

def gerar_planilha_excel(nome_arquivo: str, dados_json: str) -> str:
    """Cria um arquivo de planilha Excel (.xlsx) a partir de dados em JSON. Use para organizar dados em tabelas.
    Args:
        nome_arquivo (str): O nome do arquivo a ser gerado (ex: 'Dados.xlsx').
        dados_json (str): Uma string JSON. Deve ser um dicionário onde cada chave é o nome de uma aba da planilha e o valor é uma lista de listas, onde a primeira lista interna é o cabeçalho.
    Returns:
        str: O caminho do arquivo gerado ou uma mensagem de erro.
    """
    logger.info(f"Gerando planilha Excel: {nome_arquivo}")
    try:
        dados = json.loads(dados_json)
        with pd.ExcelWriter(nome_arquivo, engine='openpyxl') as writer:
            for nome_aba, linhas in dados.items():
                if not linhas: continue
                df = pd.DataFrame(linhas[1:], columns=linhas[0])
                df.to_excel(writer, sheet_name=nome_aba, index=False)
        return nome_arquivo
    except Exception as e:
        return f"Erro ao gerar planilha: {e}"

# --- 4. CONFIGURAÇÃO DO MODELO DE IA (VERSÃO DEFINITIVA) ---
model = None
try:
    if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, TAVILY_API_KEY]):
        raise ValueError("Uma ou mais chaves de API estão faltando no ambiente.")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name="models/gemini-pro-latest",
        tools=[tavily_search, gerar_pdf_avancado, gerar_planilha_excel],
        system_instruction=(
            "Seu nome é Alfred. Você é um mentor de vida, um conselheiro pragmático e experiente. Sua abordagem é sempre calma, lógica e focada em soluções. Você é educado e respeitoso, mas suas respostas são diretas e sem rodeios, valorizando o tempo e a clareza. Sua comunicação é um modelo de eficiência: simples, direta e sempre educada. Você não usa jargões ou metáforas forçadas. Você vai direto ao ponto, oferecendo conselhos práticos e acionáveis. Você é um guia, não um guru. Responda sempre em português do Brasil."
        )
    )
    logger.info("Modelo de IA configurado com sucesso com o conjunto completo de ferramentas.")
except Exception as e:
    logger.critical(f"FALHA CRÍTICA NA INICIALIZAÇÃO DO MODELO: {e}")

# --- 5. LÓGICA PRINCIPAL DO BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model:
        await update.message.reply_text("Perdão, Senhor. Estou com uma falha crítica na minha configuração inicial e não posso operar. A equipe técnica foi notificada.")
        return
    context.chat_data.clear()
    await update.message.reply_text("Olá, Senhor. O que deseja?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model:
        await update.message.reply_text("Perdão, Senhor. A falha crítica na minha configuração inicial persiste.")
        return
        
    user_message = update.message.text
    chat_id = update.effective_chat.id
    if not user_message: return

    await update.message.chat.send_action(action='typing')
    try:
        if 'chat' not in context.chat_data:
            context.chat_data['chat'] = model.start_chat(enable_automatic_function_calling=True)
        
        chat = context.chat_data['chat']
        response = chat.send_message(user_message)
        
        # Lógica de execução de ferramentas
        if response.function_calls:
            for function_call in response.function_calls:
                tool_name = function_call.name
                args = function_call.args
                logger.info(f"IA solicitou a ferramenta '{tool_name}' com os argumentos: {args}")
                
                # Mapeia o nome da ferramenta para a função Python real
                tool_function = {
                    "tavily_search": tavily_search,
                    "gerar_pdf_avancado": gerar_pdf_avancado,
                    "gerar_planilha_excel": gerar_planilha_excel,
                }.get(tool_name)

                if tool_function:
                    # Executa a função e obtém o resultado
                    function_response = tool_function(**args)
                    
                    # Se a função retornou um caminho de arquivo (PDF/Excel)
                    if tool_name in ["gerar_pdf_avancado", "gerar_planilha_excel"]:
                        if "Erro" not in function_response:
                            await context.bot.send_document(chat_id=chat_id, document=open(function_response, 'rb'))
                            os.remove(function_response) # Limpa o arquivo do servidor
                        else:
                            await update.message.reply_text(f"Perdão, Senhor. Falhei ao tentar gerar o arquivo. Detalhe: {function_response}")
                        return # Encerra o fluxo após enviar o arquivo ou erro
            
            # Após executar todas as ferramentas (no caso da busca), envia a resposta final da IA
            final_response = chat.history[-1].parts[0].text
            await update.message.reply_text(final_response)
            return

        # Se não houve chamada de ferramenta, apenas envia a resposta de texto
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Erro inesperado no handle_message: {e}")
        await update.message.reply_text(f"Contratempo detectado. Detalhe técnico: {e}")

# --- 6. PONTO DE ENTRADA ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Iniciando bot Alfred - Versão Definitiva.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
