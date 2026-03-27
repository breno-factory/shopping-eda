__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from pathlib import Path
import pandas as pd
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "iguatemi" / "documentos_chunkados_iguatemi.parquet"
CHROMA_DIR = PROJECT_ROOT / "data" / "processed" / "iguatemi" / "chroma_db"

df = pd.read_parquet(INPUT_PATH)

df = df[df["chunk_texto"].notna()].copy()
df = df[df["chunk_texto"].astype(str).str.strip() != ""].copy()

client = chromadb.PersistentClient(path=str(CHROMA_DIR))

embedding_fn = SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

collection = client.get_or_create_collection(
    name="iguatemi_ri",
    embedding_function=embedding_fn
)

ids = df["chunk_id"].astype(str).tolist()
documents = df["chunk_texto"].astype(str).tolist()

metadatas = []
for _, row in df.iterrows():
    metadatas.append({
        "empresa": str(row["empresa"]),
        "ano": str(row["ano"]),
        "tipo_material": str(row["tipo_material"]),
        "periodo_ref": str(row["periodo_ref"]) if pd.notna(row["periodo_ref"]) else "",
        "nome_arquivo": str(row["nome_arquivo"]),
        "caminho_relativo": str(row["caminho_relativo"]),
        "chunk_index": int(row["chunk_index"]),
    })

# limpa e recria os dados da collection
existing = collection.count()
if existing > 0:
    batch = collection.get(include=[])
    if batch and "ids" in batch and batch["ids"]:
        collection.delete(ids=batch["ids"])

batch_size = 100

for i in range(0, len(ids), batch_size):
    collection.add(
        ids=ids[i:i + batch_size],
        documents=documents[i:i + batch_size],
        metadatas=metadatas[i:i + batch_size]
    )

print(f"Chunks indexados no Chroma: {collection.count()}")
print(f"Diretório do banco: {CHROMA_DIR}")