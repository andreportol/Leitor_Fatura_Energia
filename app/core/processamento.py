# ===================================================================
# processamento.py - VERSÃO PRO (com CHUNKING + PROMPT COMPLETO)
# IA 100% estável, sem corte de texto, leitura corrigida de:
# - Energia Ativa Injetada (valor e kWh)
# - Mês de referência
# - Saldo acumulado
# ===================================================================

from __future__ import annotations
import os
import json
import re
from pathlib import Path
from typing import Union, IO, Dict, Any, List

import pdfplumber
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


# ================================================================
# CONFIGURAÇÃO
# ================================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1").strip() or "gpt-4.1"

# ================================================================
# UTILITÁRIOS
# ================================================================
def br_to_float(s: Any) -> float:
    """Aceita string, float ou int e devolve float."""
    if s is None:
        return 0.0
    if isinstance(s, (float, int)):
        return float(s)

    s = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


def float_to_br(v: Any, casas: int = 2) -> str:
    """Converte float → BR sempre retornando string, mesmo se vier string."""
    if v is None:
        return "0,00"

    # já é string → só normaliza
    if isinstance(v, str):
        v = v.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            v = float(v)
        except:
            return "0,00"

    # aqui v já é float
    txt = f"{float(v):.{casas}f}"
    return txt.replace(".", ",")



def chunk_text(text: str, size: int = 8000) -> List[str]:
    """Divide texto em pedaços menores para evitar truncamento."""
    return [text[i:i+size] for i in range(0, len(text), size)]

# ================================================================
# PDF → TEXTO
# ================================================================
def extrair_texto(pdf_path: Union[str, Path, IO[bytes]]) -> str:
    if hasattr(pdf_path, "read"):
        pdf_path.seek(0)
        pdf_file = pdf_path
    else:
        pdf_file = Path(pdf_path)

    partes = []
    with pdfplumber.open(pdf_file) as pdf:
        for pag in pdf.pages:
            words = pag.extract_words()
            if words:
                partes.append(" ".join(w["text"] for w in words))

    return "\n".join(partes)

# ================================================================
# HINTS VIA REGEX
# ================================================================
def extrair_nome(texto: str) -> str:
    padrao = r"([A-ZÁÉÍÓÚÃÕÇ]{3,}(?: [A-ZÁÉÍÓÚÃÕÇ]{2,}){1,})\s+\d{2}/\d{2}/\d{4}"
    m = re.search(padrao, texto)
    if m:
        nome = m.group(1)
        if "DOCUMENTO" not in nome and "NOTA FISCAL" not in nome:
            return nome
    return ""

def extrair_endereco(texto: str) -> str:
    m = re.search(r"(RUA [A-Z0-9ÁÉÍÓÚÃÕÇ\s\.]+,\s*\d+[^A-Z]+)", texto, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""

def extrair_uc(texto: str) -> str:
    m = re.findall(r"10/\d{7,8}-\d", texto)
    return m[0] if m else ""

def extrair_data_emissao(texto: str) -> str:
    m = re.search(r"DATA DE EMISSÃO:?(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else ""

def extrair_data_vencimento(texto: str) -> str:
    m = re.search(r"[A-Za-zÁÉÍÓÚÃÕÇ]+ ?/\s*\d{4}\s+(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else ""

def extrair_leituras(texto: str):
    m = re.search(
        r"Leitura Anterior:(\d{2}/\d{2}/\d{4}).*?Leitura Atual:(\d{2}/\d{2}/\d{4})",
        texto,
        flags=re.DOTALL
    )
    return (m.group(1), m.group(2)) if m else ("", "")

def extrair_consumo_kwh(texto: str) -> str:
    for m in re.finditer(r"KWH\s*([\d\.]+,\d{2})", texto):
        janela = texto[max(0, m.start()-80) : m.start()]
        if "Energia Atv Injetada" not in janela:
            return m.group(1)
    return ""

def extrair_preco_unitario(texto: str) -> str:
    m = re.search(r"Consumo em kWh.*?(\d,\d{5,})", texto, flags=re.DOTALL)
    return m.group(1) if m else ""

def extrair_historico_consumo(texto: str) -> List[Dict[str, str]]:
    matches = re.findall(r"([A-Z]{3}/\d{2})\s+(\d+,\d{2})", texto)
    return [{"mes": m[0], "consumo": m[1]} for m in matches]

def extrair_mes_referencia(texto: str) -> str:
    padroes = [
        r"([A-ZÇÃÉÍÓÚ]+ ?/ ?\d{4})",
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
        r"Saldo Acumulado[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        flags=re.IGNORECASE
    )
    if m:
        return m.group(1)
    m2 = re.search(r"Saldo[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})", texto)
    return m2.group(1) if m2 else ""

# ================================================================
# PROMPT COM CHUNKS (NUNCA TRUNCA!)
# ================================================================
def call_llm_fatura(texto_pdf: str, hints: Dict[str, Any]) -> Dict[str, Any]:

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
        timeout=80,
        max_retries=3,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    # 🔥 SYSTEM MESSAGE — regras completas
    regras = """
Você é especialista em leitura de faturas ENERGISA.

REGRAS PARA ENERGIA ATIVA INJETADA:
- Ler SOMENTE dentro de “Itens da Fatura”.
- Somar TODOS os valores NEGATIVOS associados a “Energia Atv Injetada GDI”.
- Retornar energia_atv_injetada_valor como POSITIVO.
- energia_atv_injetada_kwh = energia_atv_injetada_valor / preco_unitario.
- Se houver divergência, recalcular até que os valores sejam 100% consistentes.

REGRAS GERAIS:
- Datas no formato DD/MM/AAAA.
- histórico_de_consumo como lista de objetos.
- mes_referencia deve priorizar padrões como “SET/2025”, “AGOSTO/2025”, “Referente a:”.
- saldo_acumulado deve ser lido exatamente como aparece (incluindo sinal).
- Responda SOMENTE com JSON.
    """

    mensagens = [
        {"role": "system", "content": regras},
        {"role": "user", "content": "HINTS:\n" + json.dumps(hints, ensure_ascii=False)}
    ]

    partes = chunk_text(texto_pdf, size=9000)
    for i, p in enumerate(partes):
        mensagens.append({
            "role": "user",
            "content": f"TEXTO DA FATURA - PARTE {i+1}:\n{p}"
        })

    print("\n===== PROMPT (MENSAGENS ENVIADAS) =====")
    for m in mensagens:
        print(f"\n[{m['role']}]\n{m['content'][:1000]}...\n")

    resposta = llm.invoke(mensagens)
    conteudo = resposta.content

    print("\n===== RESPOSTA RAW DA IA =====")
    print(conteudo, "\n")

    return json.loads(conteudo)

# ================================================================
# CÁLCULO
# ================================================================
def calcular_economia_valor(kwh: str, preco: str):
    k = br_to_float(kwh)
    p = br_to_float(preco)
    if k <= 0 or p <= 0:
        return "", ""
    base = k * p
    return float_to_br(base * 0.3), float_to_br(base * 0.7)

# ================================================================
# PROCESSAMENTO PRINCIPAL
# ================================================================
def processar_pdf(pdf_path: Union[str, Path, IO[bytes]]) -> Dict[str, Any]:

    print("\n=========== PROCESSANDO PDF ===========")

    texto = extrair_texto(pdf_path)
    print("\n======= TEXTO EXTRAÍDO (preview) =======")
    print(texto[:1500], "...\n")

    # HINTS
    nome_hint = extrair_nome(texto)
    endereco_hint = extrair_endereco(texto)
    uc_hint = extrair_uc(texto)
    emissao_hint = extrair_data_emissao(texto)
    vencimento_hint = extrair_data_vencimento(texto)
    leitura_ant_hint, leitura_atual_hint = extrair_leituras(texto)
    consumo_hint = extrair_consumo_kwh(texto)
    preco_hint = extrair_preco_unitario(texto)
    mes_ref_hint = extrair_mes_referencia(texto)
    saldo_hint = extrair_saldo_acumulado(texto)
    hist_hint = extrair_historico_consumo(texto)

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
        "mes_referencia": mes_ref_hint,
        "saldo_acumulado": saldo_hint,
        "historico_de_consumo": hist_hint,
    }

    print("===== HINTS =====")
    print(json.dumps(hints, indent=2, ensure_ascii=False), "\n")

    ia = call_llm_fatura(texto, hints)

    print("\n===== JSON RECEBIDO DA IA =====")
    print(json.dumps(ia, indent=2, ensure_ascii=False), "\n")

    # PROCESSAMENTO FINAL
    energia_kwh = ia.get("energia_atv_injetada_kwh", "")
    preco_final = ia.get("preco_unitario", "")
    economia, pagar = calcular_economia_valor(energia_kwh, preco_final)

    resultado = {
        "nome_do_cliente": ia.get("nome_do_cliente", nome_hint),
        "endereco": ia.get("endereco", endereco_hint),
        "codigo_do_cliente_uc": ia.get("codigo_do_cliente_uc", uc_hint),
        "data_de_emissao": ia.get("data_de_emissao", emissao_hint),
        "data_de_vencimento": ia.get("data_de_vencimento", vencimento_hint),
        "leitura_anterior": ia.get("leitura_anterior", leitura_ant_hint),
        "leitura_atual": ia.get("leitura_atual", leitura_atual_hint),

        "consumo_kwh": ia.get("consumo_kwh", consumo_hint),
        "preco_unitario": preco_final,

        "energia_atv_injetada_kwh": energia_kwh,
        "energia_atv_injetada_valor": ia.get("energia_atv_injetada_valor", ""),

        "economia": economia or ia.get("economia", ""),
        "valor_a_pagar": pagar or ia.get("valor_a_pagar", ""),

        "mes_referencia": ia.get("mes_referencia", mes_ref_hint),
        "saldo_acumulado": ia.get("saldo_acumulado", saldo_hint),

        "historico_de_consumo": ia.get("historico_de_consumo", hist_hint),
    }

    print("\n====== RESULTADO FINAL ======")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print("=================================\n")

    return resultado
