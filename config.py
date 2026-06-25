"""Configuracoes centrais do projeto Probabilidades FC."""

from pathlib import Path

RAIZ = Path(__file__).parent

# Onde os dados ficam salvos
PASTA_DADOS = RAIZ / "dados"
PASTA_SITE = RAIZ / "docs"   # 'docs' = pasta que o GitHub Pages publica
PASTA_CACHE = RAIZ / "cache"

for _p in (PASTA_DADOS, PASTA_SITE, PASTA_CACHE):
    _p.mkdir(exist_ok=True)

# Ligas que vamos acompanhar.
# 'fbref' = nome usado pela lib soccerdata; 'temporada' no formato do FBref.
LIGAS = {
    "copa_mundo": {
        "nome": "Copa do Mundo 2026",
        "fbref": "INT-World Cup",
        "temporada": "2026",
        "emoji": "🌍",
    },
    "brasileirao_a": {
        "nome": "Brasileirão Série A",
        "fbref": "BRA-Serie A",
        "temporada": "2026",
        "emoji": "🇧🇷",
    },
    "brasileirao_b": {
        "nome": "Brasileirão Série B",
        "fbref": "BRA-Serie B",
        "temporada": "2026",
        "emoji": "🥈",
    },
}

# Quantos jogos recentes consideramos pra "forma" do time
JANELA_JOGOS = 8
