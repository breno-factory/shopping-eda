from pathlib import Path
import argparse
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def obter_argumentos():
    parser = argparse.ArgumentParser(description="Gera chunks dos documentos extraídos por empresa.")
    parser.add_argument(
        "--empresa",
        required=True,
        choices=["iguatemi", "multiplan", "allos", "jhsf"],
        help="Empresa a ser processada."
    )
    return parser.parse_args()


def chunk_text(texto: str, chunk_size: int = 1200, chunk_overlap: int = 200):
    if not texto or not isinstance(texto, str):
        return []

    texto = texto.strip()
    if not texto:
        return []

    chunks = []
    start = 0
    text_len = len(texto)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = texto[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        start = end - chunk_overlap

    return chunks


args = obter_argumentos()
empresa = args.empresa

INPUT_PATH = PROJECT_ROOT / "data" / "processed" / empresa / f"documentos_extraidos_{empresa}.parquet"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / empresa
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(INPUT_PATH)

registros = []

for _, row in df.iterrows():
    texto = row.get("texto_extraido", "")
    chunks = chunk_text(texto, CHUNK_SIZE, CHUNK_OVERLAP)

    for idx, chunk in enumerate(chunks, start=1):
        registros.append({
            "chunk_id": f"{row['empresa']}_{row['ano']}_{row['tipo_material']}_{row['nome_arquivo']}_{idx}",
            "empresa": row["empresa"],
            "ano": row["ano"],
            "tipo_material": row["tipo_material"],
            "periodo_ref": row["periodo_ref"],
            "nome_arquivo": row["nome_arquivo"],
            "caminho_relativo": row["caminho_relativo"],
            "chunk_index": idx,
            "chunk_texto": chunk,
            "chunk_num_caracteres": len(chunk)
        })

df_chunks = pd.DataFrame(registros)

parquet_path = OUTPUT_DIR / f"documentos_chunkados_{empresa}.parquet"
csv_path = OUTPUT_DIR / f"documentos_chunkados_{empresa}.csv"

df_chunks.to_parquet(parquet_path, index=False)
df_chunks.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(f"Empresa: {empresa}")
print(f"Chunks gerados: {len(df_chunks)}")
print(f"CSV: {csv_path}")
print(f"Parquet: {parquet_path}")

if not df_chunks.empty:
    print("\nResumo por tipo_material:")
    print(df_chunks.groupby("tipo_material").size())

    print("\nExemplo de chunk:")
    print(df_chunks.iloc[0]["chunk_texto"][:500])