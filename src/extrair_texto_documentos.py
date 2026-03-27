from pathlib import Path
import pandas as pd
import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTARIO_PATH = PROJECT_ROOT / "metadata" / "inventario_iguatemi.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "iguatemi"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extrair_pdf(caminho: Path) -> str:
    texto_paginas = []
    with fitz.open(caminho) as doc:
        for pagina in doc:
            texto_paginas.append(pagina.get_text("text"))
    return "\n".join(texto_paginas).strip()

def extrair_txt(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8", errors="ignore").strip()

def identificar_periodo(caminho_relativo: str):
    partes = caminho_relativo.split("/")
    for parte in partes:
        parte_upper = parte.upper()
        if parte_upper in {"1T24", "2T24", "3T24", "4T24", "1T25", "2T25", "3T25", "4T25"}:
            return parte_upper
    return None

df = pd.read_csv(INVENTARIO_PATH)

registros = []

for _, row in df.iterrows():
    extensao = str(row["extensao"]).lower()
    caminho = Path(row["caminho_completo"])

    if extensao not in [".pdf", ".txt", ".md"]:
        continue

    status = "ok"
    erro = None
    texto = ""

    try:
        if extensao == ".pdf":
            texto = extrair_pdf(caminho)
        elif extensao in [".txt", ".md"]:
            texto = extrair_txt(caminho)
    except Exception as e:
        status = "erro"
        erro = str(e)
        texto = ""

    registros.append({
        "empresa": row["empresa"],
        "ano": row["ano"],
        "tipo_material": row["tipo_material"],
        "periodo_ref": identificar_periodo(row["caminho_relativo"]),
        "nome_arquivo": row["nome_arquivo"],
        "extensao": extensao,
        "caminho_relativo": row["caminho_relativo"],
        "texto_extraido": texto,
        "num_caracteres": len(texto),
        "status_extracao": status,
        "erro": erro
    })

df_saida = pd.DataFrame(registros)

parquet_path = OUTPUT_DIR / "documentos_extraidos_iguatemi.parquet"
csv_path = OUTPUT_DIR / "documentos_extraidos_iguatemi.csv"

df_saida.to_parquet(parquet_path, index=False)
df_saida.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(f"Documentos processados: {len(df_saida)}")
print(f"Saída CSV: {csv_path}")
print(f"Saída Parquet: {parquet_path}")

if not df_saida.empty:
    print("\nResumo por status:")
    print(df_saida["status_extracao"].value_counts(dropna=False))

    print("\nResumo por tipo_material:")
    print(df_saida.groupby("tipo_material").size())
