from __future__ import annotations

import json
import os
from pathlib import Path
from typing import IO, List, Union

import httpx
import pdfplumber
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from openai import APITimeoutError


# ============================================================
# CARREGAR .ENV
# ============================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY não definida no ambiente!")

# MODELOS DEFINITIVOS
# gpt-4.1 é mais capaz; gpt-4o fica como fallback mais rápido
PRIMARY_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1").strip() or "gpt-4.1"
FALLBACK_2 = "gpt-4o"

OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "80"))
OPENAI_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "1"))
PDF_MAX_CHARS = int(os.getenv("PDF_TEXT_MAX_CHARS", "6000"))
# Limite moderado para reduzir cortes de resposta
MAX_COMPLETION_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "1100"))


# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================
def _cleanup_json(text: str) -> str:
    """Extrai apenas o JSON válido do retorno do modelo."""
    if not text:
        return ""

    text = text.strip()

    # remove ```json e cercas
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    # recorta apenas o bloco JSON
    ini = text.find("{")
    fim = text.rfind("}")
    if ini != -1 and fim != -1 and fim > ini:
        return text[ini:fim + 1]

    return text


def _model_builder(model: str):
    """Cria uma instância configurada do LLM."""
    return ChatOpenAI(
        model=model,
        api_key=OPENAI_API_KEY,
        temperature=0.2,
        timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_RETRIES,
        model_kwargs={
            "response_format": {"type": "json_object"},
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        },
    )


def _safe_invoke(llm, prompt: str):
    """Executa o modelo com segurança."""
    try:
        return llm.invoke(prompt)
    except (APITimeoutError, httpx.TimeoutException):
        raise TimeoutError("Timeout ao chamar OpenAI")
    except Exception as e:
        raise RuntimeError(f"Erro ao invocar modelo: {e}")


# ============================================================
# SCHEMAS DE VALIDAÇÃO
# ============================================================
class HistoricoItem(BaseModel):
    mes: str = ""
    consumo: str = ""

    @field_validator("consumo", mode="before")
    def fix_consumo(cls, v):
        return "" if v is None else str(v)


class FaturaSchema(BaseModel):
    """Define o JSON exato esperado pelo template."""
    model_config = ConfigDict(populate_by_name=True)

    nome_do_cliente: str = Field("", alias="nome do cliente")
    data_de_emissao: str = Field("", alias="data de emissao")
    data_de_vencimento: str = Field("", alias="data de vencimento")
    codigo_do_cliente_uc: str = Field("", alias="codigo do cliente - uc")
    mes_de_referencia: str = Field("", alias="mes de referencia")
    consumo_kwh: str = Field("", alias="consumo kwh")
    valor_a_pagar: str = Field("", alias="valor a pagar")
    economia: str = Field("", alias="Economia")
    historico_de_consumo: List[HistoricoItem] = Field(default_factory=list, alias="historico de consumo")
    saldo_acumulado: str = Field("", alias="saldo acumulado")
    preco_unit_com_tributos: str = Field("", alias="preco unit com tributos")
    energia_atv_injetada: str = Field("", alias="Energia Atv Injetada")


# ============================================================
# PROMPT TEMPLATE FINAL
# ============================================================
PROMPT_TEMPLATE = PromptTemplate.from_template(
    """Você é um assistente especializado em leitura de faturas de energia elétrica.
Receberá abaixo o TEXTO EXTRAÍDO DE UM PDF (pode conter ruídos, quebras e colunas desordenadas).
Sua tarefa é identificar e retornar um JSON com os campos EXATOS abaixo:

- "nome do cliente"
- "data de emissao"
- "data de vencimento"
- "codigo do cliente - uc"
- "mes de referencia"
- "consumo em kwh"
- "valor a pagar"
- "Economia" 
- "historico de consumo" (lista de objetos com "mes" e "consumo" em ordem cronológica se possível)
- "saldo acumulado"
- "preco unit com tributos"
- "Energia Atv Injetada"


Orientações específicas:
- "nome do cliente": geralmente aparece após "PAGADOR" ou destacado próximo ao endereço do cliente.
- "codigo do cliente - uc": normalize para o formato "10/########-#". Prefira valores já com "10/" na fatura (ex.: "10/33525227-0"). Se só houver versões fragmentadas (ex.: "3352527-2025-9-6"), reconstrua removendo sufixos extras e aplicando o prefixo "10/" com o dígito verificador mais plausível.
- "consumo em kwh": Está em itens de fatura, próximo de KWH que está na coluna Unid.
- "historico de consumo": extraia pares de mês e consumo da seção CONSUMO DOS ÚLTIMOS 13 meses ou da lista "Consumo FATURADO".
Quando números e meses estiverem em colunas diferentes, faça a correspondência
usando proximidade e ordem: valores mais recentes devem ser ligados aos meses mais recentes
e meses sem valor claramente identificado devem receber "".
- "preco unit com tributos": busque o valor decimal da coluna "Preço unit (R$) com tributos" com valor aproximado de 1,108630.
*Atenção para os calculos de "valor a pagar" e "economia" abaixo*.
- "Energia Atv Injetada": identifique todas as linhas de energia ativa injetada (Energia Atv Injetada), ela está em itens da fatura, e some as quantidades e divida pelo preco unit com tributos. Remova sinais negativos, normalize para o formato brasileiro e desconsidere valores que não estejam explicitamente ligados à energia injetada.
- "valor a pagar": calcule como `valor a pagar = Valor (R$) * 0.7`. O Valor (R$) sempre será negativo na fatura.
- "Economia":  Calcule `Economia = Valor (R$) * 0.3`.O Valor (R$) sempre será negativo na fatura. Formate com vírgula e duas casas decimais; se não encontrar os componentes necessários, retorne "".


Regras importantes:
0. Use pistas como "PAGADOR", "DATA DO DOCUMENTO", "VENCIMENTO", "NOTA FISCAL Nº", "MATRÍCULA", "Consumo em kWh", "VALOR DO DOCUMENTO" e "Energia Atv Injetada GDI".
1. Analise cuidadosamente números que apareçam junto a descrições; selecione o valor mais plausível.
2. Se houver múltiplos candidatos, escolha o que esteja mais próximo da descrição do campo.
3. Converta valores numéricos para o padrão brasileiro com vírgula como separador decimal.
4. Só utilize "" quando realmente não houver valor legível no texto.
5. O histórico deve ser uma lista — mesmo vazia — nunca uma string.
6. Responda **somente** com o JSON final, sem comentários ou textos adicionais.
7. Quando números e meses estiverem em colunas separadas, faça a correspondência respeitando
   a ordem cronológica (meses mais recentes com valores mais recentes).
8. Não invente "0,00" para consumo ausente — se não houver valor explícito, use "".
9. Ignore sequências de "0,00" sem rótulo claro; trate-as como ruído.
10. "codigo do cliente - uc" deve sempre começar com "10/" e ter apenas um hífen final para o dígito verificador (ex.: "10/33525227-0").
11. Antes de realizar cálculos, converta os valores extraídos para números (substituindo vírgula por ponto), execute as operações e depois formate novamente com vírgula e duas casas decimais.
12. Ao calcular "valor a pagar" e "Economia", mantenha o resultado com duas casas decimais e formato brasileiro e positivos.
13. Tanto Energia Atv Injetada  e Consumo em kWh estão em "Itens de Fatura" na coluna Quant. São valores positivos.
14. Valor (R$) está em Itens de Fatura e é negativo.
Texto a ser analisado:
----------------------
{{ text_pdf }}
----------------------
""",
    template_format="jinja2",
)


# ============================================================
# LEITURA DO PDF
# ============================================================
def ler_pdf(caminho: Union[str, Path, IO[bytes]]) -> str:
    if hasattr(caminho, "seek"):
        caminho.seek(0)

    partes = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt:
                partes.append(txt.strip())

    return "\n\n".join(partes)


# ============================================================
# EXECUÇÃO COM FALLBACK INTELIGENTE
# ============================================================
def executar_prompt(prompt: str):
    modelos = [PRIMARY_MODEL, FALLBACK_2]

    for modelo in modelos:
        try:
            print(f"[LLM] Tentando modelo: {modelo}")
            llm = _model_builder(modelo)
            resposta = _safe_invoke(llm, prompt)
            return resposta
        except Exception as e:
            print(f"[LLM] Erro no modelo {modelo}: {e}")

    raise RuntimeError("Nenhum modelo conseguiu responder.")


# ============================================================
# EXTRAÇÃO FINAL DO JSON
# ============================================================
def extrair_dados(texto: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(text_pdf=texto)

    resposta = executar_prompt(prompt)

    conteudo = getattr(resposta, "content", "")
    json_txt = _cleanup_json(conteudo)

    try:
        dados_raw = json.loads(json_txt)
    except Exception:
        raise ValueError(f"JSON inválido retornado pelo modelo:\n{json_txt[:300]}")

    try:
        obj = FaturaSchema.model_validate(dados_raw)
    except ValidationError as e:
        raise ValueError(f"JSON não corresponde ao schema esperado: {e}")

    return obj.model_dump(by_alias=True)


# ============================================================
# PROCESSAMENTO PRINCIPAL DO PDF
# ============================================================
def processar_pdf(caminho_pdf: Union[str, Path, IO[bytes]]) -> dict:
    texto = ler_pdf(caminho_pdf)

    nome = getattr(caminho_pdf, "name", str(caminho_pdf))
    print(f"[PDF] Processando: {nome}")

    if not texto.strip():
        raise ValueError("Nenhum texto extraído do PDF.")

    # Railway-safe truncate
    if len(texto) > PDF_MAX_CHARS:
        texto = texto[:PDF_MAX_CHARS]

    print(f"[PDF] Preview: {texto[:200]}...")

    resultado = extrair_dados(texto)
    try:
        preview = json.dumps(resultado, ensure_ascii=False)
        energia_injetada = resultado.get("Energia Atv Injetada", "")
        print(f"[LLM resultado] Energia Atv Injetada: {energia_injetada} | {preview[:800]}")
    except Exception:
        print("[LLM resultado] (falha ao serializar resultado para log)")

    return resultado
