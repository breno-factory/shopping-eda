from pathlib import Path
import argparse
import pandas as pd
import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def obter_argumentos():
    parser = argparse.ArgumentParser(description="Extrai texto dos documentos por empresa.")
    parser.add_argument(
        "--empresa",
        required=True,
        choices=["iguatemi", "multiplan", "allos", "jhsf"],
        help="Empresa a ser processada."
    )
    return parser.parse_args()


def extrair_pdf(caminho: Path) -> str:
    texto_paginas = []
    with fitz.open(caminho) as doc:
        for pagina in doc:
            texto_paginas.append(pagina.get_text("text"))
    return "\n".join(texto_paginas).strip()


def extrair_txt(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8", errors="ignore").strip()


def extrair_xlsx(caminho: Path) -> str:
    textos = []

    xls = pd.ExcelFile(caminho)
    for aba in xls.sheet_names:
        try:
            df = pd.read_excel(caminho, sheet_name=aba)
            df = df.fillna("")
            texto_aba = f"\n### ABA: {aba} ###\n"
            texto_aba += df.astype(str).to_string(index=False)
            textos.append(texto_aba)
        except Exception as e:
            textos.append(f"\n### ABA: {aba} ###\nErro ao ler aba: {e}")

    return "\n\n".join(textos).strip()


def identificar_periodo(caminho_relativo: str):
    partes = caminho_relativo.split("/")
    for parte in partes:
        parte_upper = parte.upper()
        if parte_upper in {"1T24", "2T24", "3T24", "4T24", "1T25", "2T25", "3T25", "4T25"}:
            return parte_upper
    return None


args = obter_argumentos()
empresa = args.empresa

INVENTARIO_PATH = PROJECT_ROOT / "metadata" / empresa / f"inventario_{empresa}.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / empresa
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INVENTARIO_PATH)

registros = []

for _, row in df.iterrows():
    extensao = str(row["extensao"]).lower()
    caminho = Path(row["caminho_completo"])

    if extensao not in [".pdf", ".txt", ".md", ".xlsx"]:
        continue

    status = "ok"
    erro = None
    texto = ""

    try:
        if extensao == ".pdf":
            texto = extrair_pdf(caminho)
        elif extensao in [".txt", ".md"]:
            texto = extrair_txt(caminho)
        elif extensao == ".xlsx":
            texto = extrair_xlsx(caminho)
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

parquet_path = OUTPUT_DIR / f"documentos_extraidos_{empresa}.parquet"
csv_path = OUTPUT_DIR / f"documentos_extraidos_{empresa}.csv"

df_saida.to_parquet(parquet_path, index=False)
df_saida.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(f"Empresa: {empresa}")
print(f"Documentos processados: {len(df_saida)}")
print(f"Saída CSV: {csv_path}")
print(f"Saída Parquet: {parquet_path}")

if not df_saida.empty:
    print("\nResumo por status:")
    print(df_saida["status_extracao"].value_counts(dropna=False))

    print("\nResumo por tipo_material:")
    print(df_saida.groupby("tipo_material").size())