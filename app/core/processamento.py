# ===================================================================
# processamento.py - VERSÃO FINAL (Regex + IA GPT-4.1)
# com PRINTS completos e leitura independente do kWh injetado
# ===================================================================

from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Union, IO, Any, Dict, List

import pdfplumber
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# -------------------------------------------------------------------
# CONFIGURAÇÃO
# -------------------------------------------------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1").strip() or "gpt-4.1"


# ===================================================================
# FUNÇÕES UTILITÁRIAS – CONVERSÃO BR ↔ float
# ===================================================================

def br_to_float(s: Any) -> float:
    """
    Converte string para float em formato brasileiro.
    Aceita float, int, strings com vírgulas, etc.
    """
    if s is None:
        return 0.0
    if isinstance(s, (float, int)):
        return float(s)

    v = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return float(v)
    except:
        return 0.0


def float_to_br(valor: Any, casas: int = 2) -> str:
    if valor is None:
        return "0,00"
    try:
        f = float(valor)
    except:
        return str(valor)
    return f"{f:.{casas}f}".replace(".", ",")


# ===================================================================
# PDF → TEXTO LINEAR
# ===================================================================

def extrair_texto(pdf_path: Union[str, Path, IO[bytes]]) -> str:
    if hasattr(pdf_path, "read"):
        pdf_path.seek(0)
        pdf_file = pdf_path
    else:
        pdf_file = Path(pdf_path)

    partes = []
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            words = pagina.extract_words()
            if words:
                linha = " ".join([w["text"] for w in words])
                partes.append(linha)

    return "\n".join(partes)


# ===================================================================
# REGEX – EXTRAÇÕES (HINTS)
# ===================================================================

def extrair_nome(texto: str) -> str:
    padrao = r"([A-ZÁÉÍÓÚÃÕÇ]{3,}(?: [A-ZÁÉÍÓÚÃÕÇ]{2,}){1,})\s+\d{2}/\d{2}/\d{4}"
    m = re.search(padrao, texto)
    if not m:
        return ""
    nome = m.group(1).strip()
    if "DOCUMENTO" in nome or "NOTA FISCAL" in nome:
        return ""
    return nome


def extrair_endereco(texto: str) -> str:
    m = re.search(r"(RUA [A-Z0-9ÁÉÍÓÚÃÕÇ\s\.]+,\s*\d+\s*-\s*\d{8})",
                  texto, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""


def extrair_uc(texto: str) -> str:
    achou = re.findall(r"10/\d{7,8}-\d", texto)
    return achou[0] if achou else ""


def extrair_data_emissao(texto):
    m = re.search(r"DATA DE EMISSÃO:?(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else ""


def extrair_data_vencimento(texto):
    m = re.search(r"[A-Za-zÁÉÍÓÚÃÕÇ]+ ?/\d{4}\s+(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else ""


def extrair_leituras(texto):
    m = re.search(
        r"Leitura Anterior:(\d{2}/\d{2}/\d{4}).*?Leitura Atual:(\d{2}/\d{2}/\d{4})",
        texto,
        flags=re.DOTALL
    )
    return (m.group(1), m.group(2)) if m else ("", "")


def extrair_consumo_kwh(texto):
    for m in re.finditer(r"KWH\s*([\d\.]+,\d{2})", texto):
        inicio = max(0, m.start() - 80)
        contexto = texto[inicio:m.start()]
        if "Energia Atv Injetada" not in contexto:
            return m.group(1)
    return ""


def extrair_preco_unitario(texto):
    m = re.search(r"Consumo em kWh.*?(\d,\d{5,})", texto, flags=re.DOTALL)
    return m.group(1) if m else ""


def extrair_historico_consumo(texto):
    matches = re.findall(r"([A-Z]{3}/\d{2})\s+(\d+,\d{2})", texto)
    return [{"mes": m[0], "consumo": m[1]} for m in matches]


def extrair_mes_referencia(texto: str) -> str:
    padroes = [
        r"([A-ZÇÃÉÍÓÚ]+ ?/ ?\d{4})",
        r"([A-ZÇÃÉÍÓÚ]+/\d{4})",
        r"([A-ZÇÃÉÍÓÚ]+ ?- ?\d{4})",
        r"Referente a[: ]+([A-ZÇÃÉÍÓÚ]+/?\d{4})",
    ]
    for p in padroes:
        m = re.search(p, texto)
        if m:
            return m.group(1).strip()
    hist = extrair_historico_consumo(texto)
    return hist[0]["mes"] if hist else ""


def extrair_saldo_acumulado(texto: str) -> str:
    m = re.search(
        r"Saldo Acumulado(?: anterior)?[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        flags=re.IGNORECASE
    )
    if m:
        return m.group(1)
    m2 = re.search(r"Saldo[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})", texto, flags=re.IGNORECASE)
    return m2.group(1) if m2 else ""


# ===================================================================
# IA – Leitura inteligente da fatura
# ===================================================================

def call_llm_fatura(texto_pdf: str, hints: Dict[str, Any]) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
        timeout=90,
        max_retries=2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    # 🔥 PROMPT DEFINITIVO — COMPLETÍSSIMO
    prompt = f"""
Você é especialista em leitura de faturas ENERGISA.

===========================
INSTRUÇÃO CRÍTICA DEFINITIVA
===========================
Leia SOMENTE dentro de “Itens da Fatura” todas as linhas contendo:
    “Energia Atv Injetada GDI”

Cada linha sempre contém DOIS valores importantes:

1) Quantidade (kWh)
   - Sempre um valor POSITIVO.
   - Pode estar na coluna “Quant.” ou ao lado da tarifa.
   - Se houver mais de uma linha, SOME todos os valores POSITIVOS.
   - Se houver valor explícito de kWh, este valor deve ser usado SEMPRE.

2) Valor (R$)
   - Sempre aparece NEGATIVO no PDF.
   - No JSON deve retornar POSITIVO.
   - Se houver várias linhas, SOMAR todos os valores.

REGRAS OBRIGATÓRIAS:
- Se existir kWh explícito → use apenas ele.
- Se NÃO existir kWh explícito → calcular:
      energia_atv_injetada_kwh = soma_valores / preco_unitario
- energia_atv_injetada_valor = soma dos valores negativos, retornado POSITIVO.

===========================
OUTROS CAMPOS
===========================
- mês de referência: detectar padrões como “SET / 2025”, “AGOSTO/2025”, “Referente a: ...”
- saldo acumulado: retornar exatamente como aparece no texto
- economia = energia_atv_injetada_valor * 0.3
- valor_a_pagar = energia_atv_injetada_valor * 0.7

===========================
FORMATO JSON FINAL
===========================
{{
 "nome_do_cliente": "",
 "endereco": "",
 "codigo_do_cliente_uc": "",
 "data_de_emissao": "",
 "data_de_vencimento": "",
 "leitura_anterior": "",
 "leitura_atual": "",
 "consumo_kwh": "",
 "preco_unitario": "",
 "energia_atv_injetada_kwh": "",
 "energia_atv_injetada_valor": "",
 "historico_de_consumo": [],
 "economia": "",
 "valor_a_pagar": "",
 "mes_referencia": "",
 "saldo_acumulado": ""
}}

DICAS (hints):
{json.dumps(hints, ensure_ascii=False)}

TEXTO DA FATURA:
\"\"\"{texto_pdf}\"\"\"

Retorne SOMENTE o JSON.
"""

    print("\n\n===== PROMPT ENVIADO À IA =====")
    print(prompt[:1800], "...\n")

    resposta = llm.invoke(prompt)
    conteudo = resposta.content

    print("\n===== RESPOSTA RAW DA IA =====")
    print(conteudo, "\n")

    return json.loads(conteudo)


# ===================================================================
# CÁLCULO DE ECONOMIA
# ===================================================================

def calcular_economia_valor(valor_injetado: Any):
    v = br_to_float(valor_injetado)
    if v <= 0:
        return "", ""
    return float_to_br(v * 0.3), float_to_br(v * 0.7)


# ===================================================================
# PROCESSAMENTO PRINCIPAL
# ===================================================================

def processar_pdf(pdf_path: Union[str, Path, IO[bytes]]) -> Dict[str, Any]:

    print("\n=========== PROCESSANDO PDF ===========")

    texto = extrair_texto(pdf_path)

    print("\n======= TEXTO EXTRAÍDO (preview) =======")
    print(texto[:1500], "...\n")

    # HINTS
    hints = {
        "nome_do_cliente": extrair_nome(texto),
        "endereco": extrair_endereco(texto),
        "codigo_do_cliente_uc": extrair_uc(texto),
        "data_de_emissao": extrair_data_emissao(texto),
        "data_de_vencimento": extrair_data_vencimento(texto),
        "leitura_anterior": extrair_leituras(texto)[0],
        "leitura_atual": extrair_leituras(texto)[1],
        "consumo_kwh": extrair_consumo_kwh(texto),
        "preco_unitario": extrair_preco_unitario(texto),
        "mes_referencia": extrair_mes_referencia(texto),
        "saldo_acumulado": extrair_saldo_acumulado(texto),
        "historico_de_consumo": extrair_historico_consumo(texto),
        "energia_atv_injetada_kwh": "",
        "energia_atv_injetada_valor": "",
    }

    print("===== HINTS (REGEX) =====")
    print(json.dumps(hints, indent=2, ensure_ascii=False), "\n")

    # IA
    ia = call_llm_fatura(texto, hints)

    print("\n===== JSON BRUTO RECEBIDO DA IA =====")
    print(json.dumps(ia, indent=2, ensure_ascii=False), "\n")

    # Normalização
    energia_valor = ia.get("energia_atv_injetada_valor")
    kwh_final = ia.get("energia_atv_injetada_kwh")

    # Cálculos finais
    economia, pagar = calcular_economia_valor(energia_valor)

    resultado = {
        "nome_do_cliente": ia.get("nome_do_cliente", hints["nome_do_cliente"]),
        "endereco": ia.get("endereco", hints["endereco"]),
        "codigo_do_cliente_uc": ia.get("codigo_do_cliente_uc", hints["codigo_do_cliente_uc"]),
        "data_de_emissao": ia.get("data_de_emissao", hints["data_de_emissao"]),
        "data_de_vencimento": ia.get("data_de_vencimento", hints["data_de_vencimento"]),
        "leitura_anterior": ia.get("leitura_anterior", hints["leitura_anterior"]),
        "leitura_atual": ia.get("leitura_atual", hints["leitura_atual"]),
        "consumo_kwh": ia.get("consumo_kwh", hints["consumo_kwh"]),
        "preco_unitario": ia.get("preco_unitario", hints["preco_unitario"]),
        "energia_atv_injetada_kwh": kwh_final,
        "energia_atv_injetada_valor": energia_valor,
        "economia": economia or ia.get("economia", ""),
        "valor_a_pagar": pagar or ia.get("valor_a_pagar", ""),
        "mes_referencia": ia.get("mes_referencia", hints["mes_referencia"]),
        "saldo_acumulado": ia.get("saldo_acumulado", hints["saldo_acumulado"]),
        "historico_de_consumo": ia.get("historico_de_consumo", hints["historico_de_consumo"]),
    }

    print("\n====== RESULTADO FINAL CONSOLIDADO ======")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print("=================================\n")

    return resultado
