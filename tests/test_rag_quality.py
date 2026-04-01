from src.rag_utils import extrair_periodo, inferir_tipos_prioritarios


def test_query_resultados_1t25():
    pergunta = "Quais foram os principais resultados do 1T25?"
    
    periodo = extrair_periodo(pergunta)
    tipos = inferir_tipos_prioritarios(pergunta)

    assert periodo == "1T25"
    assert "apresentacao_resultados" in tipos


def test_query_itr():
    pergunta = "Quais pontos aparecem no ITR do 2T25?"

    periodo = extrair_periodo(pergunta)
    tipos = inferir_tipos_prioritarios(pergunta)

    assert periodo == "2T25"
    assert tipos == ["itr_dfp"]


def test_query_estrategia():
    pergunta = "O que a empresa falou sobre estratégia no 4T24?"

    tipos = inferir_tipos_prioritarios(pergunta)

    assert "apresentacao_resultados" in tipos
