"""Configuracoes centrais do projeto Probabilidades FC."""

from pathlib import Path

from motor.forca import ParametrosLiga

RAIZ = Path(__file__).parent

# Onde os dados ficam salvos
PASTA_DADOS = RAIZ / "dados"
PASTA_SITE = RAIZ / "docs"   # 'docs' = pasta que o GitHub Pages publica
PASTA_CACHE = RAIZ / "cache"

for _p in (PASTA_DADOS, PASTA_SITE, PASTA_CACHE):
    _p.mkdir(exist_ok=True)

# Ligas que vamos acompanhar. Os ids da fonte de dados ficam em dados/scores365.py.
LIGAS = {
    "copa_mundo": {
        "nome": "Copa do Mundo 2026",
        "emoji": "🌍",
    },
    "brasileirao_a": {
        "nome": "Brasileirão Série A",
        "emoji": "🇧🇷",
    },
    "brasileirao_b": {
        "nome": "Brasileirão Série B",
        "emoji": "🥈",
    },
}

# Parametros estatisticos POR LIGA.
# Copa do Mundo = campo neutro (sem vantagem de casa); medias internacionais mais baixas.
# Brasileirao = vantagem de casa real do futebol brasileiro.
PARAMETROS_LIGA = {
    "copa_mundo": ParametrosLiga(
        media_gols_mandante=1.35, media_gols_visitante=1.35,
        media_escanteios_time=5.0, media_cartoes_time=2.2,
        peso_prior=5.0, campo_neutro=True,
    ),
    "brasileirao_a": ParametrosLiga(
        media_gols_mandante=1.45, media_gols_visitante=1.05,
        media_escanteios_time=5.0, media_cartoes_time=2.8,
        peso_prior=5.0,
    ),
    "brasileirao_b": ParametrosLiga(
        media_gols_mandante=1.40, media_gols_visitante=1.00,
        media_escanteios_time=4.8, media_cartoes_time=3.0,
        peso_prior=5.0,
    ),
}


def parametros_da_liga(liga_key: str) -> ParametrosLiga:
    return PARAMETROS_LIGA.get(liga_key, ParametrosLiga())
