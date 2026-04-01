import re
from typing import Any

SCORE_DESCARTE = -999.0
BONUS_APRESENTACAO_PERGUNTA_ABERTA = 3.0


def titulo_empresa(nome_empresa: str, nomes_empresas: dict[str, str]) -> str:
    """Retorna o nome amigável da empresa para exibição na interface."""
    return nomes_empresas.get(nome_empresa, nome_empresa.title())


def extrair_periodo(pergunta: str) -> str | None:
    """Extrai período no formato 1T25/4T24 a partir da pergunta."""
    pergunta = pergunta.upper().strip()

    match = re.search(r"\b([1-4]T\d{2})\b", pergunta)
    if match:
        return match.group(1)

    match_long = re.search(r"\b([1-4])T(20\d{2})\b", pergunta)
    if match_long:
        tri = match_long.group(1)
        ano = match_long.group(2)[-2:]
        return f"{tri}T{ano}"

    return None


def inferir_tipos_prioritarios(pergunta: str) -> list[str] | None:
    """Infere os tipos de material mais relevantes com base na pergunta."""
    p = pergunta.lower()

    if any(k in p for k in ["estratégia", "estrategia", "guidance", "plano"]):
        return ["apresentacao_resultados", "transcricao_teleconferencia"]

    if any(k in p for k in ["apresentação", "apresentacao", "slides"]):
        return ["apresentacao_resultados"]

    if any(k in p for k in ["relatório", "relatorio", "release"]):
        return ["relatorio_resultados"]

    if any(
        k in p
        for k in [
            "destaques",
            "resultado",
            "resultados",
            "guidance",
            "performance",
            "ebitda",
            "receita",
            "margem",
            "lucro",
            "vendas",
        ]
    ):
        return ["apresentacao_resultados", "relatorio_resultados"]

    if any(k in p for k in ["teleconferência", "teleconferencia", "call", "transcrição", "transcricao"]):
        return ["transcricao_teleconferencia", "audio_teleconferencia"]

    if any(
        k in p
        for k in [
            "itr",
            "dfp",
            "informações trimestrais",
            "informacoes trimestrais",
            "formulário",
            "formulario",
            "balanço",
            "balanco",
        ]
    ):
        return ["itr_dfp"]

    if any(k in p for k in ["planilha", "fundamentos", "excel"]):
        return ["planilha_fundamentos"]

    return None


def montar_where(periodo_ref: str | None = None, tipos: list[str] | None = None) -> dict[str, Any] | None:
    """Monta o filtro where do Chroma a partir de período e tipos."""
    filtros: list[dict[str, Any]] = []

    if periodo_ref:
        filtros.append({"periodo_ref": periodo_ref})

    if tipos:
        if len(tipos) == 1:
            filtros.append({"tipo_material": tipos[0]})
        else:
            filtros.append({"tipo_material": {"$in": tipos}})

    if not filtros:
        return None

    if len(filtros) == 1:
        return filtros[0]

    return {"$and": filtros}


def contar_linhas_tabeladas(texto: str) -> int:
    """Conta indícios de linhas com padrão tabular/financeiro."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    padroes = 0
    for linha in linhas[:40]:
        if re.search(r"\bR\$\b", linha):
            padroes += 1
        if re.search(r"\d[\d\.,%]+\b", linha):
            padroes += 1
        if re.search(r"\b\d{1,3}(\.\d{3})*(,\d+)?%?\b", linha):
            padroes += 1
    return padroes


def contar_linhas_indice(texto: str) -> int:
    """Conta linhas que se parecem com índice/sumário."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    qtd = 0
    for linha in linhas[:40]:
        if "...." in linha or "..." in linha:
            qtd += 1
        if re.search(r"\.{3,}\s*\d+\s*$", linha):
            qtd += 1
        if re.search(r"^\d+\s*$", linha):
            qtd += 1
    return qtd


def parece_sumario(texto: str) -> bool:
    """Indica se o texto parece ser um sumário/índice."""
    t = texto.lower()
    palavras = ["sumário", "sumario", "índice", "indice"]
    hits = sum(1 for p in palavras if p in t)
    return hits > 0


def score_chunk(chunk_text: str, pergunta: str, meta: dict[str, Any] | None = None) -> float:
    """Calcula score heurístico para reranqueamento de chunks recuperados."""
    if not chunk_text or len(chunk_text.strip()) < 50:
        return SCORE_DESCARTE

    linhas = chunk_text.splitlines()
    linhas_curtas = [l for l in linhas if len(l.strip()) < 20]
    if len(linhas) > 0 and len(linhas_curtas) / len(linhas) > 0.4:
        return SCORE_DESCARTE

    score = 0.0
    texto = chunk_text.lower()
    pergunta_l = pergunta.lower()
    meta = meta or {}

    termos_pergunta = [t for t in pergunta_l.split() if len(t) > 2]
    score += sum(1 for t in termos_pergunta if t in texto) * 1.5

    sinais_explicativos = [
        "crescimento", "aumento", "redução", "queda", "variação",
        "resultado", "receita", "ebitda", "margem", "ocupação",
        "inadimplência", "vendas", "desempenho", "impacto",
        "destaque", "destaques", "avançou", "evoluiu", "registrou",
    ]
    score += sum(1 for s in sinais_explicativos if s in texto) * 0.8

    sinais_estruturais = ["sumário", "índice", "anexo", "table of contents"]
    score -= sum(1 for s in sinais_estruturais if s in texto) * 2.0

    sinais_disclaimer = [
        "este documento pode conter",
        "declarações prospectivas",
        "forward-looking statements",
        "não constitui oferta",
        "informações sujeitas a",
        "disclaimer",
    ]
    score -= sum(1 for s in sinais_disclaimer if s in texto) * 2.5

    if texto.count("|") >= 4 or texto.count("\t") >= 3:
        score -= 2.0

    if chunk_text.count("\n") > 15:
        score -= 2.0

    proporcao_numeros = 0.0
    palavras = texto.split()
    if palavras:
        proporcao_numeros = sum(1 for p in palavras if any(c.isdigit() for c in p)) / len(palavras)

        if proporcao_numeros > 0.20:
            score -= 2.5

        media_palavra = sum(len(p) for p in palavras) / len(palavras)
        if media_palavra < 4:
            score -= 3.0

    sinais_genericos = [
        "a companhia apresenta",
        "o documento apresenta",
        "conforme demonstrado",
        "informações adicionais",
        "para mais informações",
        "vide tabela abaixo",
    ]
    score -= sum(1 for s in sinais_genericos if s in texto) * 1.2

    if any(p in texto for p in ["anexos", "portfólio", "portfolio", "destaques"]) and proporcao_numeros > 0.15:
        score -= 2.5

    if contar_linhas_indice(chunk_text) > 3:
        score -= 3.0

    if contar_linhas_tabeladas(chunk_text) > 5:
        score -= 3.0

    if parece_sumario(chunk_text):
        score -= 2.5

    if len(palavras) > 80:
        score += 1.0

    sinais_causalidade = [
        "devido",
        "por conta",
        "explicado",
        "impactado",
        "impulsionado",
        "reflexo",
        "resultado de",
        "em função",
    ]
    score += sum(1 for s in sinais_causalidade if s in texto) * 1.5

    if "ebitda" in texto and not any(s in texto for s in sinais_causalidade):
        score -= 1.0

    if proporcao_numeros > 0.15 and not any(s in texto for s in sinais_explicativos):
        score -= 3.0

    if chunk_text.count("(") >= 8 or chunk_text.count(")") >= 8:
        score -= 4.0

    if len(re.findall(r"\(?\d[\d\.\,]*\)?", chunk_text)) > 20:
        score -= 4.0

    sinais_tabela_financeira = [
        "demais ajustes",
        "variação nos ativos e passivos",
        "contas a receber",
        "imóveis a comercializar",
        "estoques",
        "caixa e equivalentes",
        "passivos",
        "ativos",
    ]
    if sum(1 for s in sinais_tabela_financeira if s in texto) >= 2:
        score -= 4.0

    if meta.get("tipo_material") == "planilha_fundamentos":
        score -= 4.0

    return score


def reranquear_resultados(pergunta: str, resultado: dict[str, Any]) -> list[dict[str, Any]]:
    """Reranqueia resultados do Chroma usando score heurístico e contexto da pergunta."""
    documentos = resultado.get("documents", [[]])[0]
    metadados = resultado.get("metadatas", [[]])[0]
    distancias = resultado.get("distances", [[]])[0]

    pergunta_l = pergunta.lower()
    itens: list[dict[str, Any]] = []

    for doc, meta, dist in zip(documentos, metadados, distancias):
        meta = meta or {}
        score = score_chunk(doc, pergunta, meta)

        if meta.get("tipo_material") == "apresentacao_resultados" and any(
            k in pergunta_l for k in ["principais resultados", "destaques", "performance"]
        ):
            score += BONUS_APRESENTACAO_PERGUNTA_ABERTA

        itens.append(
            {
                "doc": doc,
                "meta": meta,
                "dist": dist,
                "score_final": score,
            }
        )

    itens.sort(key=lambda x: x["score_final"], reverse=True)
    return itens
