from typing import Final

EMPRESAS_DISPONIVEIS: Final[list[str]] = ["iguatemi", "multiplan", "allos", "jhsf"]

NOMES_EMPRESAS: Final[dict[str, str]] = {
    "iguatemi": "Iguatemi",
    "multiplan": "Multiplan",
    "allos": "Allos",
    "jhsf": "JHSF",
}

PERGUNTAS_EXEMPLO: Final[dict[str, list[str]]] = {
    "iguatemi": [
        "Quais foram os principais resultados do 4T24?",
        "O que a teleconferência do 4T24 falou sobre estratégia?",
        "Quais pontos financeiros aparecem no ITR do 2T24?",
    ],
    "multiplan": [
        "Quais foram os principais resultados do 4T24?",
        "O que explica a variação do EBITDA no 2T24?",
        "O que impulsionou o crescimento das vendas no 4T24?",
    ],
    "allos": [
        "Quais foram os principais resultados do 1T25?",
        "O que a teleconferência do 2T25 falou sobre estratégia?",
        "Quais pontos financeiros aparecem no ITR do 3T25?",
    ],
    "jhsf": [
        "Quais foram os principais resultados do 1T25?",
        "Quais foram os destaques do 1T25?",
        "O que a apresentação do 3T25 destacou?",
    ],
}