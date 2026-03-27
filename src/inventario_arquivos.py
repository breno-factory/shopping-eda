from pathlib import Path
import pandas as pd
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = PROJECT_ROOT / "data" / "raw" / "iguatemi"
OUTPUT_DIR = PROJECT_ROOT / "metadata"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

registros = []

for arquivo in BASE_DIR.rglob("*"):
    if arquivo.is_file():
        partes = arquivo.relative_to(BASE_DIR).parts

        ano = partes[0] if len(partes) > 0 else None
        tipo_material = partes[1] if len(partes) > 1 else None

        stat = arquivo.stat()

        registros.append({
            "empresa": "iguatemi",
            "ano": ano,
            "tipo_material": tipo_material,
            "nome_arquivo": arquivo.name,
            "extensao": arquivo.suffix.lower(),
            "caminho_completo": str(arquivo),
            "caminho_relativo": str(arquivo.relative_to(BASE_DIR)),
            "tamanho_bytes": stat.st_size,
            "data_modificacao": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

df = pd.DataFrame(registros)

df = df.sort_values(
    by=["ano", "tipo_material", "nome_arquivo"],
    na_position="last"
).reset_index(drop=True)

csv_path = OUTPUT_DIR / "inventario_iguatemi.csv"
parquet_path = OUTPUT_DIR / "inventario_iguatemi.parquet"

df.to_csv(csv_path, index=False, encoding="utf-8-sig")
df.to_parquet(parquet_path, index=False)

print(f"Inventário gerado com {len(df)} arquivos.")
print(f"CSV: {csv_path}")
print(f"Parquet: {parquet_path}")