__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from pathlib import Path
import re
import chromadb
import streamlit as st
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


PROJECT_ROOT = Path(__file__).resolve().parent
CHROMA_DIR = PROJECT_ROOT / "data" / "processed" / "iguatemi" / "chroma_db"


st.set_page_config(
    page_title="POC RI Shopping Centers – Iguatemi",
    page_icon="📊",
    layout="wide"
)


@st.cache_resource
def carregar_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    collection = client.get_collection(
        name="iguatemi_ri",
        embedding_function=embedding_fn
    )

    return collection


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


def consultar(collection, pergunta, where=None, n_results=15):
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


st.title("📊 POC RI Shopping Centers – Iguatemi")

with st.sidebar:
    st.subheader("Configurações")
    n_resultados = st.slider("Quantidade de resultados finais", min_value=3, max_value=10, value=5)
    n_busca_inicial = st.slider("Quantidade de chunks buscados antes do reranqueamento", min_value=5, max_value=30, value=15)
    mostrar_filtros = st.checkbox("Mostrar filtros inferidos", value=False)
    mostrar_scores = st.checkbox("Mostrar score e distância", value=False)

pergunta = st.text_input(
    "Digite sua pergunta",
    placeholder="Ex.: Quais foram os principais resultados do 4T24?"
)

st.markdown(
    """
**Exemplos de perguntas**
1. Quais foram os principais resultados do 4T24?
2. O que a teleconferência do 4T24 falou sobre estratégia?
3. Quais pontos financeiros aparecem no ITR do 2T24?
"""
)

col1, col2 = st.columns([1, 1])
consultar_btn = col1.button("Consultar", use_container_width=True)
limpar_btn = col2.button("Limpar", use_container_width=True)

if limpar_btn:
    st.rerun()

if consultar_btn:
    if not pergunta.strip():
        st.warning("Digite uma pergunta para consultar.")
    else:
        if not CHROMA_DIR.exists():
            st.error(f"O diretório do Chroma não foi encontrado: {CHROMA_DIR}")
        else:
            try:
                collection = carregar_collection()

                periodo_ref = extrair_periodo(pergunta)
                tipos_prioritarios = inferir_tipos_prioritarios(pergunta)
                where = montar_where(periodo_ref=periodo_ref, tipos=tipos_prioritarios)

                if mostrar_filtros:
                    with st.expander("Filtros inferidos", expanded=False):
                        st.write({
                            "periodo_ref": periodo_ref,
                            "tipos_prioritarios": tipos_prioritarios,
                            "where": where
                        })

                with st.spinner("Consultando base vetorial..."):
                    resultado_filtrado = consultar(
                        collection=collection,
                        pergunta=pergunta,
                        where=where,
                        n_results=n_busca_inicial
                    )

                    itens_filtrados = reranquear_resultados(pergunta, resultado_filtrado)

                    if not itens_filtrados:
                        resultado_amplo = consultar(
                            collection=collection,
                            pergunta=pergunta,
                            where=None,
                            n_results=n_busca_inicial
                        )
                        itens_filtrados = reranquear_resultados(pergunta, resultado_amplo)

                st.subheader("Resultados")

                if not itens_filtrados:
                    st.info("Nenhum resultado encontrado.")
                else:
                    for i, item in enumerate(itens_filtrados[:n_resultados], start=1):
                        meta = item["meta"]
                        doc = item["doc"]

                        titulo = f"Resultado {i} | {meta.get('nome_arquivo', 'sem nome')}"
                        with st.expander(titulo, expanded=(i == 1)):
                            info_cols = st.columns(4)
                            info_cols[0].metric("Ano", meta.get("ano", ""))
                            info_cols[1].metric("Período", meta.get("periodo_ref", ""))
                            info_cols[2].metric("Tipo", meta.get("tipo_material", ""))
                            info_cols[3].metric("Chunk", meta.get("chunk_index", ""))

                            if mostrar_scores:
                                score_cols = st.columns(2)
                                score_cols[0].metric("Score final", f"{item['score_final']:.4f}")
                                score_cols[1].metric("Distância original", f"{item['dist']:.4f}")

                            st.markdown("**Arquivo**")
                            st.write(meta.get("nome_arquivo", ""))

                            st.markdown("**Caminho relativo**")
                            st.code(meta.get("caminho_relativo", ""), language="text")

                            st.markdown("**Trecho recuperado**")
                            st.write(doc[:2500])

            except Exception as e:
                st.error(f"Erro ao consultar a base: {e}")