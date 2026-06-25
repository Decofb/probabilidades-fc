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
        # mando moderado: o "mandante" do feed marca bem mais (1.89/1.04 em 56 jogos);
        # o backtest confirma a direção. Valor intermediário p/ hedge de viés de chave/anfitrião.
        media_gols_mandante=1.55, media_gols_visitante=1.15,
        media_escanteios_time=5.0, media_cartoes_time=2.2,
        peso_prior=5.0, campo_neutro=False,
    ),
    "brasileirao_a": ParametrosLiga(
        media_gols_mandante=1.45, media_gols_visitante=1.05,
        media_escanteios_time=5.0, media_cartoes_time=2.8,
        peso_prior=5.0,
    ),
    "brasileirao_b": ParametrosLiga(
        # mando corrigido pelo estudo dos 140 jogos: Série B quase não tem
        # vantagem de casa (real 1.21/1.10), e isso melhora o backtest.
        media_gols_mandante=1.20, media_gols_visitante=1.10,
        media_escanteios_time=4.8, media_cartoes_time=3.0,
        peso_prior=5.0,
    ),
}


def parametros_da_liga(liga_key: str) -> ParametrosLiga:
    return PARAMETROS_LIGA.get(liga_key, ParametrosLiga())


# Inicio da TEMPORADA atual por liga. Usado nos estudos/tendencias para nao
# misturar o fim da temporada passada (sequencias e medias ficam "puras").
import datetime as _dt  # noqa: E402

INICIO_TEMPORADA = {
    "copa_mundo": "2026-06-01",
    "brasileirao_a": "2026-01-15",
    "brasileirao_b": "2026-01-15",
}


def janela_liga(liga_key: str, dias: int = 210, hoje_date=None):
    """(d1, d2) em DD/MM/AAAA respeitando o inicio da temporada da liga."""
    hoje = hoje_date or _dt.date.today()
    d1 = hoje - _dt.timedelta(days=dias)
    ini = INICIO_TEMPORADA.get(liga_key)
    if ini:
        d_ini = _dt.date.fromisoformat(ini)
        if d_ini > d1:
            d1 = d_ini
    return d1.strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y")
