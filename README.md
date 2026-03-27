# POC RI Shopping Centers – Iguatemi

## Objetivo
Esta POC permite fazer perguntas em linguagem natural sobre materiais de RI da Iguatemi usando busca semântica local.

## O que foi feito
- inventário dos arquivos
- extração de texto dos documentos
- chunking do conteúdo
- indexação no ChromaDB
- interface Streamlit para consulta

## Estrutura principal
- `app.py` → interface Streamlit
- `src/` → scripts do pipeline
- `data/raw/iguatemi/` → arquivos brutos
- `data/processed/iguatemi/chroma_db/` → base vetorial
- `metadata/` → inventário dos arquivos

## Ambiente
- WSL Ubuntu
- Miniconda
- Python 3.11
- ambiente `iguatemi-poc`

## Tecnologias
Python
Streamlit
ChromaDB
Sentence Transformers
Docling
Pandas


## Status
42 arquivos inventariados
31 documentos processados
2621 chunks gerados
interface final funcionando

## Exemplos de perguntas
- Quais foram os principais resultados do 4T24?
- O que a teleconferência do 4T24 falou sobre estratégia?
- Quais pontos financeiros aparecem no ITR do 2T24?