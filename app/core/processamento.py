# ===================================================================
# processamento.py - VERSÃO FINAL (Regex + IA GPT-4.1)
# com PRINTS de depuração para inspeção completa
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

def br_to_float(s: str) -> float:
    if not s:
        return 0.0
    v = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(v)
    except:
        return 0.0

def float_to_br(valor: float, casas: int = 2) -> str:
    txt = f"{valor:.{casas}f}"
    return txt.replace(".", ",")

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
# REGEX – EXTRAÇÕES HEURÍSTICAS (HINTS)
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
    m = re.search(r"Leitura Anterior:(\d{2}/\d{2}/\d{4}).*?"
                  r"Leitura Atual:(\d{2}/\d{2}/\d{4})",
                  texto, flags=re.DOTALL)
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

def extrair_saldo_acumulado(texto):
    m = re.search(r"Saldo Acumulado[:\s]*([-]?\d[\d\.]*,\d{2})", texto, flags=re.IGNORECASE)
    return m.group(1) if m else ""

def extrair_mes_referencia(texto):
    m = re.search(r"(?:M[ÊE]S DE REFER[ÊE]NCIA|M[ÊE]S REFER[ÊE]NCIA|REFERENTE\s+A)\s*[:\-]?\s*([A-Z]{3}/\d{2,4})", texto, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    # fallback: usa primeiro mês do histórico encontrado
    hist = extrair_historico_consumo(texto)
    return hist[0]["mes"] if hist else ""

def extrair_mes_referencia(texto: str) -> str:
    """
    Extrai o mês de referência da fatura ENERGISA.
    Exemplos:
      'SETEMBRO / 2025'
      'SET / 2025'
      'Referente a: AGOSTO/2025'
    """
    # Padrões mais comuns
    padroes = [
        r"([A-ZÇÃÉÍÓÚ]+ ?/ ?\d{4})",        # EX.: SET / 2025
        r"([A-ZÇÃÉÍÓÚ]+ ?/\d{4})",         # EX.: SET/2025
        r"([A-ZÇÃÉÍÓÚ]+ ?- ?\d{4})",       # EX.: SET - 2025
        r"Referente a[: ]+([A-ZÇÃÉÍÓÚ]+/?\d{4})",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto)
        if m:
            return m.group(1).strip()

    return ""

def extrair_saldo_acumulado(texto: str) -> str:
    """
    Extrai o saldo acumulado da fatura.
    Pode aparecer como:
      'Saldo Acumulado: R$ 117,34'
      'Saldo acumulado anterior R$ 52,17'
      'Saldo Acumulado (Crédito) -507,75'
    """
    m = re.search(
        r"Saldo Acumulado(?: anterior)?[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        flags=re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    # fallback
    m2 = re.search(r"Saldo[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})", texto, flags=re.IGNORECASE)
    if m2:
        return m2.group(1).strip()

    return ""



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
        timeout=80,
        max_retries=2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    prompt = f"""
Você é especialista em leitura de faturas ENERGISA.

INSTRUÇÃO CRÍTICA – ENERGIA ATIVA INJETADA:
- Leia SOMENTE dentro de “Itens da Fatura”.
- Valor (R$) é sempre NEGATIVO no PDF → retornar POSITIVO no JSON.
- energia_atv_injetada_KWH = energia_atv_injetada_valor / preco_unitario.

TEMPLATE JSON:
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
 "saldo_acumulado": "",
}}

DICAS (hints):

Regras importantes (siga com rigor):
- Use apenas informações presentes no texto ou deduções matemáticas diretas.
- 'codigo_do_cliente_uc' deve ser a UC/Unidade Consumidora (ex: '10/########-#').
- Datas no formato DD/MM/AAAA.
- 'consumo_kwh': consumo principal faturado de energia ativa.
- 'preco_unitario': preço unitário em R$/kWh (formato brasileiro, ex: '1,108630').
- 'energia_atv_injetada_valor': Sempre será um valor negativo na fatura. O valor total deverá ser a soma de todos os valores negativos que tem o texto `Energia Atv Injetada GDI`.
- 'energia_atv_injetada_kwh':  É igual ao valor da `energia_atv_injetada_valor / preco_unitario`
- 'mes_referencia': deve ser lido do texto. Priorizar padrões como “SET / 2025”, “AGOSTO/2025”, “Referente a: ...”.
- 'saldo_acumulado': deve ser lido literalmente do texto, mantendo sinal.

INSTRUÇÃO CRÍTICA SOBRE ENERGIA ATIVA INJETADA (json):
- Leia a Energia Atv Injetada SOMENTE no bloco 'Itens da Fatura'.
- O valor correto de kWh é APENAS o número POSITIVO que vem imediatamente após 'KWH'.
- O valor monetário associado é o número NEGATIVO na mesma linha (ex.: '-507,75'), mas deve ser retornado POSITIVO no JSON.
- Se houver mais de um trecho de Energia Atv Injetada, some todos os kWh.

- 'energia_atv_injetada_valor': valor total R$ associado à energia injetada (positivo no JSON).
- 'historico_de_consumo': liste os meses e consumos em kWh do histórico (ex.: 'SET/25', 'AGO/25', etc).
- 'economia' e 'valor_a_pagar' podem ser calculados assim:
    base = energia_atv_injetada_kwh * preco_unitario
    economia = base * 0.3
    valor_a_pagar = base * 0.7
  Retorne-os em formato '999,99'.

Você também receberá um JSON com DICAS (hints) extraídas via regex.
Use essas dicas para confirmar ou corrigir o que você encontrar no texto.
{json.dumps(hints, ensure_ascii=False)}

TEXTO:
\"\"\"{texto_pdf}\"\"\"

Responda APENAS com JSON.
"""

    print("\n\n===== PROMPT ENVIADO À IA =====")
    print(prompt[:2000], "...\n")

    resposta = llm.invoke(prompt)
    conteudo = resposta.content

    print("\n===== RESPOSTA RAW DA IA =====")
    print(conteudo, "\n")

    return json.loads(conteudo)

# ===================================================================
# CÁLCULO DE ECONOMIA
# ===================================================================

def calcular_economia_valor(kwh: str, preco: str):
    k = br_to_float(kwh)
    p = br_to_float(preco)
    if k <= 0 or p <= 0:
        return "", ""
    base = k * p
    return float_to_br(base * 0.3), float_to_br(base * 0.7)

# ===================================================================
# PROCESSAMENTO PRINCIPAL
# ===================================================================

def processar_pdf(pdf_path: Union[str, Path, IO[bytes]]) -> Dict[str, Any]:

    print("\n=========== PROCESSANDO PDF ===========")

    texto = extrair_texto(pdf_path)
    print("\n======= TEXTO EXTRAÍDO (preview) =======")
    print(texto[:1500], "...\n")

    # Hints via regex
    nome_hint = extrair_nome(texto)
    endereco_hint = extrair_endereco(texto)
    uc_hint = extrair_uc(texto)
    emissao_hint = extrair_data_emissao(texto)
    vencimento_hint = extrair_data_vencimento(texto)
    leitura_ant_hint, leitura_atual_hint = extrair_leituras(texto)
    consumo_hint = extrair_consumo_kwh(texto)
    preco_hint = extrair_preco_unitario(texto)
    mes_referencia_hint = extrair_mes_referencia(texto)
    saldo_acumulado_hint = extrair_saldo_acumulado(texto)
    historico_hint = extrair_historico_consumo(texto)


    hints = {
        "nome_do_cliente": nome_hint,
        "endereco": endereco_hint,
        "codigo_do_cliente_uc": uc_hint,
        "data_de_emissao": emissao_hint,
        "data_de_vencimento": vencimento_hint,
        "leitura_anterior": leitura_ant_hint,
        "leitura_atual": leitura_atual_hint,
        "consumo_kwh": consumo_hint,
        "preco_unitario": preco_hint,
        "energia_atv_injetada_kwh": "",
        "energia_atv_injetada_valor": "",
        "mes_referencia": mes_referencia_hint,
        "saldo_acumulado": saldo_acumulado_hint,
        "historico_de_consumo": historico_hint,
    }

    print("===== HINTS (REGEX) =====")
    print(json.dumps(hints, indent=2, ensure_ascii=False), "\n")

    # Chamada da IA
    ia = call_llm_fatura(texto, hints)

    print("\n===== JSON BRUTO RECEBIDO DA IA =====")
    print(json.dumps(ia, indent=2, ensure_ascii=False), "\n")

    # Normalização energia injetada
    energia_raw = ia.get("energia_atv_injetada_kwh", "")
    if isinstance(energia_raw, (float, int)):
        energia_final = float_to_br(energia_raw)
    else:
        energia_final = str(energia_raw)

    economia, pagar = calcular_economia_valor(
        energia_final,
        ia.get("preco_unitario", "")
    )

    resultado = {
        "nome_do_cliente": ia.get("nome_do_cliente", nome_hint),
        "endereco": ia.get("endereco", endereco_hint),
        "codigo_do_cliente_uc": ia.get("codigo_do_cliente_uc", uc_hint),
        "data_de_emissao": ia.get("data_de_emissao", emissao_hint),
        "data_de_vencimento": ia.get("data_de_vencimento", vencimento_hint),
        "leitura_anterior": ia.get("leitura_anterior", leitura_ant_hint),
        "leitura_atual": ia.get("leitura_atual", leitura_atual_hint),
        "consumo_kwh": ia.get("consumo_kwh", consumo_hint),
        "preco_unitario": ia.get("preco_unitario", preco_hint),
        "energia_atv_injetada_kwh": energia_final,
        "energia_atv_injetada_valor": ia.get("energia_atv_injetada_valor", ""),
        "economia": economia or ia.get("economia", ""),
        "valor_a_pagar": pagar or ia.get("valor_a_pagar", ""),
        "mes_referencia": ia.get("mes_referencia", mes_referencia_hint),
        "saldo_acumulado": ia.get("saldo_acumulado", saldo_acumulado_hint),
        "historico_de_consumo": ia.get("historico_de_consumo", historico_hint),        
    }

    print("\n====== RESULTADO FINAL CONSOLIDADO ======")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print("=================================\n")

    return resultado





