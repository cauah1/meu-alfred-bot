import os
import logging
import json
import pandas as pd
import re
from datetime import datetime
import pytz
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fpdf import FPDF
import google.generativeai as genai
from tavily import TavilyClient
from openai import OpenAI

# --- 1. CONFIGURAÇÃO INICIAL ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
MEMORIA_FILE = "memoria_alfred.json"

# --- 2. CARREGAMENTO DAS CHAVES E CLIENTES ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- 3. FUNÇÕES AUXILIARES E DE GERAÇÃO ---

def extrair_json(texto: str) -> str:
    """Extrai um bloco de código JSON de uma string de texto."""
    match = re.search(r'```json\s*(\{.*?\})\s*```', texto, re.DOTALL)
    if match: return match.group(1)
    match = re.search(r'(\{.*?\})', texto, re.DOTALL)
    if match: return match.group(1)
    return texto

class PDF(FPDF):
    """Classe PDF personalizada para adicionar cabeçalho e rodapé."""
    def header(self):
        if hasattr(self, 'title') and self.title:
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, self.title, 0, 0, "C")
            self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")

def criar_arquivo_pdf(titulo_documento: str, instrucao_ia: str) -> str:
    """Função chamada pelo comando /pdf para orquestrar a criação de um PDF."""
    logger.info(f"Gerando PDF para: {instrucao_ia}")
    try:
        prompt = f"Crie o conteúdo para um documento PDF com base na seguinte instrução: '{instrucao_ia}'. Responda APENAS com uma estrutura JSON contendo uma chave 'secoes', que é uma lista de dicionários, cada um com 'titulo' e 'conteudo'."
        response = model_chat.generate_content(prompt)
        json_text = extrair_json(response.text)
        data = json.loads(json_text)
        
        pdf = PDF()
        pdf.set_title(titulo_documento)
        pdf.add_page()
        for secao in data.get('secoes', []):
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, secao.get('titulo', '').encode('latin-1', 'replace').decode('latin-1'), 0, 1, "L")
            pdf.ln(5)
            pdf.set_font("Arial", "", 12)
            conteudo = secao.get('conteudo', '').encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 10, conteudo)
            pdf.ln(10)
        
        file_path = f"{titulo_documento.replace(' ', '_')}.pdf"
        pdf.output(file_path)
        return file_path
    except Exception as e:
        logger.error(f"Erro ao criar PDF: {e}")
        return f"Erro: {e}"

def criar_arquivo_planilha(nome_arquivo: str, instrucao_ia: str) -> str:
    """Função chamada pelo comando /planilha para orquestrar a criação de uma planilha."""
    logger.info(f"Gerando Planilha para: {instrucao_ia}")
    try:
        prompt = f"Crie os dados para uma planilha com base na seguinte instrução: '{instrucao_ia}'. Responda APENAS com uma estrutura JSON. O JSON deve ser um dicionário onde cada chave é o nome de uma aba e o valor é uma lista de listas, com a primeira lista sendo o cabeçalho."
        response = model_chat.generate_content(prompt)
        json_text = extrair_json(response.text)
        dados = json.loads(json_text)

        with pd.ExcelWriter(nome_arquivo, engine='openpyxl') as writer:
            for nome_aba, linhas in dados.items():
                if not linhas: continue
                df = pd.DataFrame(linhas[1:], columns=linhas[0])
                df.to_excel(writer, sheet_name=nome_aba, index=False)
        return nome_arquivo
    except Exception as e:
        logger.error(f"Erro ao criar Planilha: {e}")
        return f"Erro: {e}"

# --- 4. CONFIGURAÇÃO DOS MODELOS E FERRAMENTAS ---
model_chat = None
model_tools = None
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- NOVAS FERRAMENTAS DE MEMÓRIA ---
def salvar_memoria(topico: str, conteudo: str) -> dict:
    """Use para salvar ou atualizar uma informação importante em sua memória de longo prazo. Sempre confirme a ação para o usuário."""
    logger.info(f"Salvando memória sobre '{topico}'")
    try:
        memorias = {}
        if os.path.exists(MEMORIA_FILE):
            with open(MEMORIA_FILE, 'r', encoding='utf-8') as f:
                memorias = json.load(f)
        memorias[topico.lower()] = conteudo
        with open(MEMORIA_FILE, 'w', encoding='utf-8') as f:
            json.dump(memorias, f, ensure_ascii=False, indent=4)
        return {"status": f"A informação sobre '{topico}' foi salva com sucesso."}
    except Exception as e:
        return {"error": str(e)}

def ler_memoria(topico: str) -> dict:
    """Use para consultar sua memória de longo prazo sobre um tópico específico ANTES de tentar outras ferramentas. Se o tópico não for encontrado, retorne uma mensagem indicando isso."""
    logger.info(f"Lendo memória sobre '{topico}'")
    try:
        if not os.path.exists(MEMORIA_FILE):
            return {"resultado": "Nenhuma memória encontrada sobre este tópico."}
        with open(MEMORIA_FILE, 'r', encoding='utf-8') as f:
            memorias = json.load(f)
        conteudo = memorias.get(topico.lower())
        if conteudo:
            return {"resultado": f"Lembrança sobre '{topico}': {conteudo}"}
        else:
            return {"resultado": f"Nenhuma memória encontrada sobre o tópico '{topico}'."}
    except Exception as e:
        return {"error": str(e)}

# --- FERRAMENTAS EXISTENTES ---
def tavily_search(query: str) -> dict:
    """Busca informações em tempo real na internet sobre um tópico ou pergunta."""
    logger.info(f"Executando busca autônoma para: '{query}'")
    try:
        response = tavily_client.search(query=query, search_depth="basic", max_results=3)
        return {"result": "\n\n".join([f"Fonte: {obj['url']}\nConteúdo: {obj['content']}" for obj in response['results']])}
    except Exception as e:
        return {"error": str(e)}

def obter_data_e_hora_atual() -> dict:
    """Retorna a data e a hora atuais."""
    logger.info("Executando ferramenta de data/hora.")
    tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(tz)
    data_formatada = now.strftime("Hoje é %A, %d de %B de %Y. A hora atual é %H:%M:%S (Horário de Brasília).")
    return {"result": data_formatada}

def analise_profunda_com_gpt(prompt: str) -> dict:
    """Use para tarefas de raciocínio lógico muito complexo."""
    logger.info(f"Consultando o especialista SÊNIOR (GPT-4o) para: '{prompt}'")
    try:
        response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Você é um especialista em análise lógica e profunda."}, {"role": "user", "content": prompt}])
        return {"result": response.choices[0].message.content}
    except Exception as e: return {"error": str(e)}

def analise_rapida_com_gpt(prompt: str) -> dict:
    """Use para obter uma segunda opinião rápida ou para brainstorming."""
    logger.info(f"Consultando o especialista JÚNIOR (GPT-3.5-Turbo) para: '{prompt}'")
    try:
        response = openai_client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "Você é um assistente rápido e eficiente."}, {"role": "user", "content": prompt}])
        return {"result": response.choices[0].message.content}
    except Exception as e: return {"error": str(e)}

try:
    if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, TAVILY_API_KEY, OPENAI_API_KEY]):
        raise ValueError("Chaves de API faltando.")
    genai.configure(api_key=GOOGLE_API_KEY)
    
    model_chat = genai.GenerativeModel(model_name="models/gemini-pro-latest", system_instruction=("Seu nome é Alfred. Você é um assistente focado em executar tarefas diretas."))
    
    model_tools = genai.GenerativeModel(
        model_name="models/gemini-pro-latest",
        tools=[salvar_memoria, ler_memoria, tavily_search, obter_data_e_hora_atual, analise_profunda_com_gpt, analise_rapida_com_gpt],
        system_instruction=(
            "Seu nome é Alfred. Você é um orquestrador de especialistas com uma memória persistente. Sua função é entender a pergunta do usuário. Se a pergunta for sobre algo que você possa ter anotado, CONSULTE SUA MEMÓRIA PRIMEIRO usando a ferramenta 'ler_memoria'. Se for para salvar algo, use 'salvar_memoria'. Para outras tarefas, decida se responde sozinho ou se delega para suas outras ferramentas: busca na web, relógio, ou os analistas GPT (rápido ou profundo). Sintetize as informações e entregue a resposta final com sua própria voz: calma, direta e sábia."
        )
    )
    
    logger.info("Modelos de IA (com memória persistente) inicializados com sucesso.")
except Exception as e:
    logger.critical(f"FALHA CRÍTICA NA INICIALIZAÇÃO DE UM DOS MODELOS: {e}")

# --- 5. LÓGICA DOS COMANDOS DO BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model_chat or not model_tools:
        await update.message.reply_text("Perdão, Senhor. Falha crítica na configuração inicial.")
        return
    context.chat_data.clear()
    await update.message.reply_text("Olá, Senhor. O que deseja? Para gerar arquivos, use os comandos /pdf ou /planilha.")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model_tools:
        await update.message.reply_text("Perdão, Senhor. Meu módulo de raciocínio está com falha.")
        return
    user_message = update.message.text
    if not user_message: return
    await update.message.chat.send_action(action='typing')
    try:
        if 'chat_tools' not in context.chat_data:
            context.chat_data['chat_tools'] = model_tools.start_chat(enable_automatic_function_calling=True)
        
        chat = context.chat_data['chat_tools']
        response = chat.send_message(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"Contratempo na conversa. Detalhe: {e}")

async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model_chat:
        await update.message.reply_text("Perdão, Senhor. Meu módulo de documentação está com falha.")
        return
    instrucao = " ".join(context.args)
    if not instrucao:
        await update.message.reply_text("Uso: /pdf <instrução para o conteúdo do PDF>")
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
    if not model_chat:
        await update.message.reply_text("Perdão, Senhor. Meu módulo de documentação está com falha.")
        return
    instrucao = " ".join(context.args)
    if not instrucao:
        await update.message.reply_text("Uso: /planilha <instrução para os dados da planilha>")
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
    
    logger.info("Iniciando bot Alfred - Versão 3.6 (Com Memória).")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
