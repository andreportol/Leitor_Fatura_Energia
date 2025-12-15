# ===================================================================
# processamento.py - VERSÃO FINAL (Regex + IA GPT-4.1)
# Foco: leitura robusta de Energia Atv. Injetada (kWh e R$),
# mês de referência e saldo acumulado.
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
    Converte string no formato brasileiro para float.
    Aceita também float/int para evitar erros de atributo.
    Ex: '1.234,56' -> 1234.56 ; '312,00' -> 312.0 ; '-507,75' -> -507.75
    """
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)

    # garante string
    s = str(s).strip()
    if not s:
        return 0.0

    v = s.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def float_to_br(valor: Any, casas: int = 2) -> str:
    """
    Converte float (ou string numérica) para string no formato brasileiro.
    Ex: 1234.5 -> '1234,50'
    """
    if isinstance(valor, str):
        valor = br_to_float(valor)
    try:
        txt = f"{float(valor):.{casas}f}"
    except Exception:
        return ""
    return txt.replace(".", ",")


# ===================================================================
# PDF → TEXTO LINEAR
# ===================================================================

def extrair_texto(pdf_path: Union[str, Path, IO[bytes]]) -> str:
    """
    Extrai texto unificado do PDF, mantendo a ordem visual o melhor possível.
    Aceita tanto caminho (Path/str) quanto InMemoryUploadedFile.
    """
    if hasattr(pdf_path, "read"):
        pdf_path.seek(0)
        pdf_file = pdf_path
    else:
        pdf_file = Path(pdf_path)

    partes: List[str] = []
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            words = pagina.extract_words()
            if words:
                linha = " ".join(w["text"] for w in words)
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
    m = re.search(
        r"(RUA [A-Z0-9ÁÉÍÓÚÃÕÇ\s\.]+,\s*\d+\s*-\s*\d{8})",
        texto,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def extrair_uc(texto: str) -> str:
    achou = re.findall(r"10/\d{7,8}-\d", texto)
    return achou[0] if achou else ""


def extrair_data_emissao(texto: str) -> str:
    m = re.search(r"DATA DE EMISSÃO:?(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else ""


def extrair_data_vencimento(texto: str) -> str:
    m = re.search(r"[A-Za-zÁÉÍÓÚÃÕÇ]+ ?/\d{4}\s+(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else ""


def extrair_leituras(texto: str) -> tuple[str, str]:
    m = re.search(
        r"Leitura Anterior:(\d{2}/\d{2}/\d{4}).*?Leitura Atual:(\d{2}/\d{2}/\d{4})",
        texto,
        flags=re.DOTALL,
    )
    if m:
        return m.group(1), m.group(2)
    return "", ""


def extrair_consumo_kwh(texto: str) -> str:
    """
    Consumo principal da fatura.
    Ignora ocorrências próximas de 'Energia Atv Injetada'.
    """
    for m in re.finditer(r"KWH\s*([\d\.]+,\d{2})", texto):
        inicio = max(0, m.start() - 80)
        contexto = texto[inicio:m.start()]
        if "Energia Atv Injetada" not in contexto:
            return m.group(1)
    return ""


def extrair_preco_unitario(texto: str) -> str:
    m = re.search(r"Consumo em kWh.*?(\d,\d{5,})", texto, flags=re.DOTALL)
    return m.group(1) if m else ""


def extrair_historico_consumo(texto: str) -> List[Dict[str, str]]:
    matches = re.findall(r"([A-Z]{3}/\d{2})\s+(\d+,\d{2})", texto)
    return [{"mes": m[0], "consumo": m[1]} for m in matches]


def extrair_mes_referencia(texto: str) -> str:
    """
    Extrai o mês de referência.
    """
    padroes = [
        r"(SETEMBRO / \d{4}|OUTUBRO / \d{4}|NOVEMBRO / \d{4}|DEZEMBRO / \d{4}|"
        r"JANEIRO / \d{4}|FEVEREIRO / \d{4}|MARÇO / \d{4}|ABRIL / \d{4}|MAIO / \d{4}|"
        r"JUNHO / \d{4}|JULHO / \d{4}|AGOSTO / \d{4})",
        r"Referente a[: ]+([A-ZÇÃÉÍÓÚ]+/?\d{4})",
        r"(?:M[ÊE]S DE REFER[ÊE]NCIA|M[ÊE]S REFER[ÊE]NCIA)\s*[:\-]?\s*([A-Z]{3}/\d{2,4})",
    ]
    for padrao in padroes:
        m = re.search(padrao, texto, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # fallback: primeiro mês do histórico
    hist = extrair_historico_consumo(texto)
    return hist[0]["mes"] if hist else ""


def extrair_saldo_acumulado(texto: str) -> str:
    """
    Extrai o saldo acumulado.
    """
    m = re.search(
        r"Saldo Acumulado(?: anterior)?[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    m2 = re.search(
        r"Saldo[^0-9\-]*([\-]?\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        flags=re.IGNORECASE,
    )
    if m2:
        return m2.group(1).strip()

    return ""


# ----------- BLOCO ITENS DA FATURA + ENERGIA ATIVA INJETADA --------

def extrair_itens_da_fatura(texto: str) -> str:
    """
    Isola o bloco 'Itens da Fatura' até algum marcador de fim.
    """
    ini = texto.find("Itens da Fatura")
    if ini == -1:
        return texto

    # tenta achar um fim razoável (histórico, consumo 13 meses, nota fiscal etc.)
    m = re.search(
        r"(Consumo dos últimos 13 meses|Consumo kWh|NOTA FISCAL|NOTA FISCAL/CONTA)",
        texto[ini:],
        flags=re.IGNORECASE,
    )
    if m:
        fim = ini + m.start()
        return texto[ini:fim]
    return texto[ini:]


def extrair_energia_injetada_valor(texto: str) -> float:
    """
    Soma TODOS os valores negativos (R$) associados a 'Energia Atv Injetada'
    dentro do bloco 'Itens da Fatura'.

    Exemplo de padrão:
        Energia Atv Injetada GDI ...
        1,108630 -7.206,16 ...

    Retorna sempre positivo (módulo da soma).
    """
    itens = extrair_itens_da_fatura(texto)

    padrao = r"Energia Atv Injetada.*?(-\d[\d\.]*,\d{2})"
    matches = re.findall(padrao, itens, flags=re.IGNORECASE | re.DOTALL)

    total = 0.0
    for v in matches:
        total += br_to_float(v)

    # total é negativo; devolvemos módulo positivo
    return abs(total)


# ===================================================================
# IA – Leitura inteligente da fatura
# ===================================================================

def call_llm_fatura(texto_pdf: str, hints: Dict[str, Any], prompt_extra: str = "") -> Dict[str, Any]:
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

    extra_block = ""
    if prompt_extra:
        extra_block = f"\nINSTRUÇÕES DO CLIENTE (priorize e siga):\n{prompt_extra}\n"

    prompt = f"""
Você é especialista em leitura de faturas ENERGISA.
{extra_block}

INSTRUÇÃO CRÍTICA – ENERGIA ATIVA INJETADA:
- Leia SOMENTE dentro de "Itens da Fatura".
- O valor em R$ da Energia Atv Injetada GDI é sempre NEGATIVO no PDF
  (ex.: -7.206,16), mas no JSON deve ser POSITIVO.
- A soma de TODOS os valores negativos relacionados a "Energia Atv Injetada"
  corresponde a "energia_atv_injetada_valor".
- A quantidade em kWh da Energia Atv Injetada é POSITIVA.
- Quando as DICAS (hints) trouxerem "energia_atv_injetada_valor" e/ou
  "energia_atv_injetada_kwh" preenchidos, COPIE exatamente esses valores
  para o JSON final (não altere, não recalcule).

TEMPLATE JSON (responda APENAS neste formato json válido):
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

DICAS (hints) extraídas via regex em json:
{json.dumps(hints, ensure_ascii=False)}

Regras importantes (siga com rigor):
- Priorize as INSTRUÇÕES DO CLIENTE para fórmulas e formato.
- Use apenas informações presentes no texto ou deduções matemáticas diretas.
- 'codigo_do_cliente_uc' deve ser a UC/Unidade Consumidora (ex: "10/########-#").
- Datas no formato DD/MM/AAAA.
- 'consumo_kwh': consumo principal faturado de energia ativa.
- 'preco_unitario': preço unitário em R$/kWh (formato brasileiro, ex: "1,108630").
- 'energia_atv_injetada_valor':
    * É a soma de TODOS os valores negativos das linhas de "Energia Atv Injetada".
    * No JSON deve ser POSITIVO.
- 'energia_atv_injetada_kwh':
    * Se as DICAS trouxerem esse valor, COPIE exatamente o valor das DICAS.
    * Caso contrário, calcule a partir da fatura (por ex. dividindo o valor
      total em R$ pelo preço unitário), garantindo que:
        energia_atv_injetada_kwh ≈ energia_atv_injetada_valor / preco_unitario
- 'mes_referencia': deve ser lido do texto. Priorizar padrões como
    "SET / 2025", "AGOSTO/2025", "Referente a: ...".
- 'saldo_acumulado': deve ser lido literalmente do texto, mantendo sinal e formato.

Para 'economia' e 'valor_a_pagar':
- Siga as instruções do cliente se ele definir fatores ou fórmulas.
- Se o cliente não definir, use a base = energia_atv_injetada_valor (em R$, valor positivo) e calcule:
    economia = base * 0.3
    valor_a_pagar = base * 0.7
- Retorne-os como string no formato brasileiro, ex.: "999,99".

TEXTO COMPLETO DA FATURA (PDF → texto):
\"\"\"{texto_pdf}\"\"\"

Responda APENAS com o JSON final, sem comentários adicionais.
"""

    print("\n\n===== PROMPT ENVIADO À IA =====")
    print(prompt[:2000], "...\n")

    resposta = llm.invoke(prompt)
    conteudo = resposta.content

    print("\n===== RESPOSTA RAW DA IA =====")
    print(conteudo, "\n")

    return json.loads(conteudo)


# ===================================================================
# CÁLCULO DE ECONOMIA a partir do VALOR (R$) da energia injetada
# ===================================================================

def calcular_economia_valor(energia_valor: str) -> tuple[str, str]:
    """
    Fallback padrão (usado só se a IA não fornecer):
      economia = energia_atv_injetada_valor * 0.3
      valor_a_pagar = energia_atv_injetada_valor * 0.7
    Retorna ambos no formato brasileiro.
    """
    v = br_to_float(energia_valor)
    if v <= 0:
        return "", ""
    economia = v * 0.3
    pagar = v * 0.7
    return float_to_br(economia), float_to_br(pagar)


# ===================================================================
# PROCESSAMENTO PRINCIPAL
# ===================================================================

def processar_pdf(pdf_path: Union[str, Path, IO[bytes]], prompt_extra: str = "") -> Dict[str, Any]:
    print("\n=========== PROCESSANDO PDF ===========")

    texto = extrair_texto(pdf_path)

    print("\n======= TEXTO EXTRAÍDO (preview) =======")
    print(texto[:1500], "...\n")

    if not texto.strip():
        raise ValueError("Nenhum texto pôde ser extraído do PDF.")

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

    # Energia Atv Injetada – valor total (R$) via regex + kWh calculado
    energia_valor_hint_float = extrair_energia_injetada_valor(texto)
    energia_valor_hint = float_to_br(energia_valor_hint_float) if energia_valor_hint_float > 0 else ""

    preco_float = br_to_float(preco_hint)
    if energia_valor_hint_float > 0 and preco_float > 0:
        kwh_hint_float = energia_valor_hint_float / preco_float
        energia_kwh_hint = float_to_br(kwh_hint_float)
    else:
        energia_kwh_hint = ""

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
        "energia_atv_injetada_kwh": energia_kwh_hint,
        "energia_atv_injetada_valor": energia_valor_hint,
        "mes_referencia": mes_referencia_hint,
        "saldo_acumulado": saldo_acumulado_hint,
        "historico_de_consumo": historico_hint,
    }

    print("===== HINTS (REGEX) =====")
    print(json.dumps(hints, indent=2, ensure_ascii=False), "\n")

    # Chamada da IA
    ia = call_llm_fatura(texto, hints, prompt_extra=prompt_extra)

    print("\n===== JSON BRUTO RECEBIDO DA IA =====")
    print(json.dumps(ia, indent=2, ensure_ascii=False), "\n")

    # ---------------- PÓS-PROCESSAMENTO / GARANTIAS -----------------

    def get_field(key: str, default: Any = "") -> Any:
        v = ia.get(key)
        if isinstance(v, str) and v.strip():
            return v
        if v not in (None, "", []):
            return v
        return default

    # Campos básicos: IA com fallback nos hints
    nome_final = get_field("nome_do_cliente", nome_hint)
    endereco_final = get_field("endereco", endereco_hint)
    uc_final = get_field("codigo_do_cliente_uc", uc_hint)
    emissao_final = get_field("data_de_emissao", emissao_hint)
    vencimento_final = get_field("data_de_vencimento", vencimento_hint)
    leitura_ant_final = get_field("leitura_anterior", leitura_ant_hint)
    leitura_atual_final = get_field("leitura_atual", leitura_atual_hint)
    consumo_final = get_field("consumo_kwh", consumo_hint)
    preco_final = get_field("preco_unitario", preco_hint)
    mes_ref_final = get_field("mes_referencia", mes_referencia_hint)
    saldo_final = get_field("saldo_acumulado", saldo_acumulado_hint)

    # Energia Atv Injetada – SEMPRE confiar no cálculo em Python se existir
    energia_valor_final = energia_valor_hint or ia.get("energia_atv_injetada_valor", "")
    if not energia_valor_final:
        energia_valor_final = ia.get("energia_atv_injetada_valor", "")

    # recalcula kWh final em cima do valor e do preço unitário
    energia_kwh_final = energia_kwh_hint
    if energia_valor_final and preco_final:
        v = br_to_float(energia_valor_final)
        p = br_to_float(preco_final)
        if v > 0 and p > 0:
            energia_kwh_final = float_to_br(v / p)

    historico_final = ia.get("historico_de_consumo", historico_hint)
    if not isinstance(historico_final, list) or not historico_final:
        historico_final = historico_hint

    # economia / valor_a_pagar – prioriza valores vindos da IA; calcula se faltar
    economia_final = ia.get("economia", "") or ""
    valor_pagar_final = ia.get("valor_a_pagar", "") or ""

    if not economia_final or not valor_pagar_final:
        economia_calc, valor_pagar_calc = calcular_economia_valor(energia_valor_final)
        if economia_calc and not economia_final:
            economia_final = economia_calc
        if valor_pagar_calc and not valor_pagar_final:
            valor_pagar_final = valor_pagar_calc

    resultado = {
        "nome_do_cliente": nome_final,
        "endereco": endereco_final,
        "codigo_do_cliente_uc": uc_final,
        "data_de_emissao": emissao_final,
        "data_de_vencimento": vencimento_final,
        "leitura_anterior": leitura_ant_final,
        "leitura_atual": leitura_atual_final,
        "consumo_kwh": consumo_final,
        "preco_unitario": preco_final,
        "energia_atv_injetada_kwh": energia_kwh_final,
        "energia_atv_injetada_valor": energia_valor_final,
        "economia": economia_final,
        "valor_a_pagar": valor_pagar_final,
        "mes_referencia": mes_ref_final,
        "saldo_acumulado": saldo_final,
        "historico_de_consumo": historico_final,
    }

    print("\n====== RESULTADO FINAL CONSOLIDADO ======")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print("=================================\n")

    return resultado


# ===================================================================
# PROCESSAMENTO ORQUESTRADO (compatível com serviço)
# ===================================================================

def processar(pdf_file: Any, cliente: Any, texto: str | None = None) -> Dict[str, Any]:
    """
    Wrapper utilizado pelo serviço de faturas para a Energisa.
    Usa o pipeline completo (regex + IA) com o prompt do cliente.
    """
    texto = texto or extrair_texto(pdf_file)
    prompt_extra = getattr(cliente, "prompt_template", "") or ""
    dados = processar_pdf(pdf_file, prompt_extra=prompt_extra) or {}

    template_fatura = getattr(cliente, "template_fatura", "") or "energisa_padrao.html"
    if getattr(cliente, "is_VIP", False) and getattr(cliente, "template_fatura", ""):
        template_fatura = cliente.template_fatura

    return {
        "cliente": cliente,
        "concessionaria": "ENERGISA",
        "dados": dados,
        "template_fatura": template_fatura,
        "texto": texto,
    }
