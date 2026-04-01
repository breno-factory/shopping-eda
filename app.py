__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from pathlib import Path

import chromadb
import streamlit as st
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from src.config import EMPRESAS_DISPONIVEIS, NOMES_EMPRESAS, PERGUNTAS_EXEMPLO
from src.rag_utils import (
    extrair_periodo,
    inferir_tipos_prioritarios,
    montar_where,
    reranquear_resultados,
    titulo_empresa,
)

PROJECT_ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="POC RI Shopping Centers",
    page_icon="📊",
    layout="wide"
)


def get_chroma_dir(empresa: str) -> Path:
    return PROJECT_ROOT / "data" / "processed" / empresa / "chroma_db"


def get_collection_name(empresa: str) -> str:
    return f"{empresa}_ri"


@st.cache_resource
def carregar_collection(chroma_dir: str, collection_name: str):
    client = chromadb.PersistentClient(path=chroma_dir)

    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    collection = client.get_collection(
        name=collection_name,
        embedding_function=embedding_fn
    )

    return collection


def consultar(collection, pergunta, where=None, n_results=15):
    kwargs = {
        "query_texts": [pergunta],
        "n_results": n_results
    }
    if where:
        kwargs["where"] = where

    return collection.query(**kwargs)


with st.sidebar:
    empresa = st.selectbox("Empresa", EMPRESAS_DISPONIVEIS)
    st.subheader("Configurações")
    n_resultados = st.slider("Quantidade de resultados finais", min_value=3, max_value=10, value=5)
    n_busca_inicial = st.slider("Quantidade de chunks buscados antes do reranqueamento", min_value=5, max_value=30, value=15)
    mostrar_filtros = st.checkbox("Mostrar filtros inferidos", value=False)
    mostrar_scores = st.checkbox("Mostrar score e distância", value=False)

CHROMA_DIR = get_chroma_dir(empresa)
COLLECTION_NAME = get_collection_name(empresa)

st.title(f"POC RI Shopping Centers – {titulo_empresa(empresa, NOMES_EMPRESAS)}")

if "pergunta" not in st.session_state:
    st.session_state["pergunta"] = ""

pergunta = st.text_input(
    "Digite sua pergunta",
    value=st.session_state["pergunta"],
    placeholder="Ex.: Quais foram os principais resultados do 4T24?",
    key="input_pergunta"
)

st.session_state["pergunta"] = pergunta

with st.expander("Exemplos de perguntas", expanded=False):
    exemplos = PERGUNTAS_EXEMPLO.get(empresa, [])

    st.markdown("**Perguntas sugeridas para esta empresa**")
    for i, exemplo in enumerate(exemplos, start=1):
        st.write(f"{i}. {exemplo}")

    st.markdown("**Clique para usar uma pergunta pronta**")
    cols_exemplos = st.columns(len(exemplos)) if exemplos else []

    for i, exemplo in enumerate(exemplos):
        if cols_exemplos[i].button(f"Usar exemplo {i+1}", key=f"btn_exemplo_{empresa}_{i}"):
            st.session_state["pergunta"] = exemplo
            st.session_state["input_pergunta"] = exemplo
            st.rerun()

col1, col2 = st.columns([1, 1])
consultar_btn = col1.button("Consultar", use_container_width=True)
limpar_btn = col2.button("Limpar", use_container_width=True)

if limpar_btn:
    st.session_state["pergunta"] = ""
    st.session_state["input_pergunta"] = ""
    st.rerun()

if consultar_btn:
    if not pergunta.strip():
        st.warning("Digite uma pergunta para consultar.")
    else:
        if not CHROMA_DIR.exists():
            st.error(f"O diretório do Chroma não foi encontrado: {CHROMA_DIR}")
        else:
            try:
                collection = carregar_collection(str(CHROMA_DIR), COLLECTION_NAME)

                periodo_ref = extrair_periodo(pergunta)
                tipos_prioritarios = inferir_tipos_prioritarios(pergunta)
                where = montar_where(periodo_ref=periodo_ref, tipos=tipos_prioritarios)

                if mostrar_filtros:
                    with st.expander("Filtros inferidos", expanded=False):
                        st.write({
                            "empresa": empresa,
                            "collection_name": COLLECTION_NAME,
                            "chroma_dir": str(CHROMA_DIR),
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

                    if not itens_filtrados and periodo_ref is not None:
                        where_periodo = {"periodo_ref": periodo_ref}
                        resultado_periodo = consultar(
                            collection=collection,
                            pergunta=pergunta,
                            where=where_periodo,
                            n_results=n_busca_inicial
                        )
                        itens_filtrados = reranquear_resultados(pergunta, resultado_periodo)

                    if not itens_filtrados and periodo_ref is None and tipos_prioritarios is None:
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