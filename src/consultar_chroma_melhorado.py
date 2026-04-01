__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from pathlib import Path
import re
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = PROJECT_ROOT / "data" / "processed" / "iguatemi" / "chroma_db"

client = chromadb.PersistentClient(path=str(CHROMA_DIR))

embedding_fn = SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

collection = client.get_collection(
    name="iguatemi_ri",
    embedding_function=embedding_fn
)

def extrair_periodo(pergunta: str):
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

def inferir_tipos_prioritarios(pergunta: str):
    p = pergunta.lower()

    if any(k in p for k in ["destaques", "resultado", "resultados", "guidance", "performance"]):
        return ["relatorio_resultados", "apresentacao_resultados"]

    if any(k in p for k in ["teleconferência", "teleconferencia", "call", "transcrição", "transcricao"]):
        return ["transcricao_teleconferencia"]

    if any(k in p for k in ["itr", "dfp", "formulário", "formulario", "balanço", "balanco", "financeiro"]):
        return ["itr_dfp"]

    return None

def montar_where(periodo_ref=None, tipos=None):
    filtros = []

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

def consultar(pergunta, where=None, n_results=15):
    kwargs = {
        "query_texts": [pergunta],
        "n_results": n_results
    }
    if where:
        kwargs["where"] = where

    return collection.query(**kwargs)

def proporcao_digitos(texto: str) -> float:
    if not texto:
        return 0.0
    total = len(texto)
    if total == 0:
        return 0.0
    qtd = sum(1 for c in texto if c.isdigit())
    return qtd / total

def contar_linhas_tabeladas(texto: str) -> int:
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
    t = texto.lower()
    palavras = ["sumário", "sumario", "índice", "indice"]
    hits = sum(1 for p in palavras if p in t)
    return hits > 0

def score_chunk(pergunta: str, meta: dict, doc: str, dist: float) -> float:
    texto = (doc or "").lower()
    pergunta_l = pergunta.lower()
    score = 0.0

    score += -float(dist)
    tipo = str(meta.get("tipo_material", ""))

    if any(k in pergunta_l for k in ["destaques", "principais resultados", "resultado", "resultados"]):
        if tipo == "apresentacao_resultados":
            score += 2.6
        elif tipo == "relatorio_resultados":
            score += 2.2
        elif tipo == "itr_dfp":
            score += 0.5

    if "guidance" in pergunta_l:
        if tipo == "apresentacao_resultados":
            score += 2.8
        elif tipo == "relatorio_resultados":
            score += 2.0
        elif tipo == "itr_dfp":
            score += 0.5

    if any(k in pergunta_l for k in ["teleconferência", "teleconferencia", "call", "transcrição", "transcricao"]):
        if tipo == "transcricao_teleconferencia":
            score += 2.0

    if any(k in pergunta_l for k in ["itr", "dfp", "balanço", "balanco", "financeiro"]):
        if tipo == "itr_dfp":
            score += 2.0

    boosts_fortes = {
        "destaques dos resultados": 2.0,
        "principais destaques": 1.8,
        "principais resultados": 1.8,
        "mensagem da administração": 1.5,
        "mensagem da administracao": 1.5,
        "principais indicadores": 1.6,
        "guidance": 1.8,
        "estratégia": 1.5,
        "estrategia": 1.5,
        "desempenho operacional e financeiro": 1.6,
        "resultado operacional": 1.4,
        "resultado financeiro": 1.4,
    }
    for termo, peso in boosts_fortes.items():
        if termo in texto:
            score += peso

    palavras_importantes = [
        "vendas", "sss", "sas", "ocupação", "ocupacao",
        "aluguel", "ebitda", "receita", "margem",
        "estratégia", "estrategia", "guidance"
    ]
    for termo in palavras_importantes:
        if termo in pergunta_l and termo in texto:
            score += 0.8

    penalidades_fortes = [
        "sumário", "sumario", "índice", "indice",
        "anexo", "anexos", "apêndice", "apendice",
        "glossário", "glossario",
        "notas explicativas",
        "demonstrações financeiras", "demonstracoes financeiras",
        "informações trimestrais", "informacoes trimestrais",
    ]
    for termo in penalidades_fortes:
        if termo in texto:
            score -= 2.5

    penalidades_medias = [
        "b3", "cvm", "auditoria", "parecer", "estatuto social"
    ]
    for termo in penalidades_medias:
        if termo in texto:
            score -= 0.7

    linhas_indice = contar_linhas_indice(texto)

    if parece_sumario(texto):
        score -= 2.0

    if linhas_indice >= 4:
        score -= 2.0
    if linhas_indice >= 8:
        score -= 3.0

    digitos = proporcao_digitos(texto)
    linhas_tabeladas = contar_linhas_tabeladas(texto)

    if digitos > 0.20:
        score -= 1.0
    if digitos > 0.30:
        score -= 1.5
    if linhas_tabeladas > 20:
        score -= 1.2
    if linhas_tabeladas > 30:
        score -= 1.8

    if 400 <= len(doc) <= 1600:
        score += 0.4

    return score

def reranquear_resultados(pergunta: str, resultado: dict):
    documentos = resultado.get("documents", [[]])[0]
    metadados = resultado.get("metadatas", [[]])[0]
    distancias = resultado.get("distances", [[]])[0]

    itens = []
    for doc, meta, dist in zip(documentos, metadados, distancias):
        score = score_chunk(pergunta, meta, doc, dist)
        itens.append({
            "doc": doc,
            "meta": meta,
            "dist": dist,
            "score_final": score
        })

    itens.sort(key=lambda x: x["score_final"], reverse=True)
    return itens

def imprimir_resultados_reranqueados(itens, titulo="RESULTADOS", top_k=5):
    print(f"\n=== {titulo} ===\n")

    if not itens:
        print("Nenhum resultado encontrado.\n")
        return 0

    for i, item in enumerate(itens[:top_k], start=1):
        meta = item["meta"]
        doc = item["doc"]

        print(f"Resultado {i}")
        print(f"Score final: {item['score_final']:.4f}")
        print(f"Distância original: {item['dist']}")
        print(f"Ano: {meta.get('ano')}")
        print(f"Tipo: {meta.get('tipo_material')}")
        print(f"Período: {meta.get('periodo_ref')}")
        print(f"Arquivo: {meta.get('nome_arquivo')}")
        print(f"Caminho: {meta.get('caminho_relativo')}")
        print("Trecho:")
        print(doc[:1200])
        print("\n" + "-" * 80 + "\n")

    return min(len(itens), top_k)

while True:
    pergunta = input("\nDigite sua pergunta (ou 'sair'): ").strip()

    if not pergunta:
        print("Pergunta vazia. Tente novamente.")
        continue

    if pergunta.lower() in {"sair", "exit", "quit"}:
        print("Encerrando consulta.")
        break

    periodo_ref = extrair_periodo(pergunta)
    tipos_prioritarios = inferir_tipos_prioritarios(pergunta)
    where = montar_where(periodo_ref=periodo_ref, tipos=tipos_prioritarios)

    print("\nFiltros inferidos:")
    print(f"periodo_ref = {periodo_ref}")
    print(f"tipos_prioritarios = {tipos_prioritarios}")
    print(f"where = {where}")

    resultado_filtrado = consultar(pergunta, where=where, n_results=15)
    itens_filtrados = reranquear_resultados(pergunta, resultado_filtrado)
    qtd = imprimir_resultados_reranqueados(
        itens_filtrados,
        titulo="RESULTADOS FILTRADOS + RERANQUEADOS",
        top_k=5
    )

    if qtd == 0:
        resultado_amplo = consultar(pergunta, where=None, n_results=15)
        itens_amplos = reranquear_resultados(pergunta, resultado_amplo)
        imprimir_resultados_reranqueados(
            itens_amplos,
            titulo="FALLBACK - BUSCA AMPLA + RERANQUEADA",
            top_k=5
        )