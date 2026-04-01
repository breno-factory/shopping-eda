import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.rag_utils import score_chunk


def test_score_chunk_premia_texto_narrativo():
    texto = """
    No 1T25, a companhia apresentou crescimento de receita, avanço de EBITDA e melhora operacional,
    impulsionada por vendas e aumento de ocupação. A performance foi resultado da estratégia de expansão,
    maior eficiência operacional e fortalecimento da receita recorrente, refletindo o aumento da margem,
    do resultado consolidado e do lucro líquido no período.
    """
    meta = {"tipo_material": "apresentacao_resultados"}
    score = score_chunk(texto, "Quais foram os principais resultados do 1T25?", meta)
    assert score > 0


def test_score_chunk_pune_texto_muito_tabelado():
    texto = """
    (403.499)
    (3.611)
    35.862
    19.424
    35.931
    61.869
    Variação nos ativos e passivos
    Contas a receber 12.136
    (11.720)
    (38.753)
    """
    meta = {"tipo_material": "relatorio_resultados"}
    score = score_chunk(texto, "Quais foram os principais resultados do 1T25?", meta)
    assert score < 0


def test_score_chunk_pune_planilha_fundamentos():
    texto = """
    Receita Bruta 332,8 mm EBITDA 147,4 mm Lucro Líquido 340,0 mm
    Receita Bruta 332,8 mm EBITDA 147,4 mm Lucro Líquido 340,0 mm
    """
    meta = {"tipo_material": "planilha_fundamentos"}
    score = score_chunk(texto, "Quais foram os principais resultados do 1T25?", meta)
    assert score < 0