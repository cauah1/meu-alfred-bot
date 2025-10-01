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
# (As funções das ferramentas permanecem as mesmas)
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

# --- 4. CONFIGURAÇÃO DO MODELO DE IA (VERSÃO ESTÁVEL) ---
model = None
try:
    if not all([TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, TAVILY_API_KEY]):
        raise ValueError("Uma ou mais chaves de API estão faltando.")
    genai.configure(api_key=GOOGLE_API_KEY)
    # INICIALIZAÇÃO SEM FERRAMENTAS - GARANTE QUE O BOT INICIE
    model = genai.GenerativeModel(
        model_name="models/gemini-pro-latest",
        system_instruction=(
            "Seu nome é Alfred. Você é um mentor de vida, um conselheiro pragmático e experiente..." # Sua persona
        )
    )
    # As ferramentas serão passadas em cada chamada, não na inicialização.
    tools = [tavily_search, gerar_pdf_avancado, gerar_planilha_excel]
    logger.info("Modelo de I
