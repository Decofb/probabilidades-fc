"""
Coletor de dados do 365scores (API JSON publica).

Vantagem sobre o FBref: nao tem Cloudflare e entrega POR PARTIDA:
  - gols (placar)
  - xG / Gols esperados      (id 76)
  - escanteios               (id 8)
  - cartoes amarelos/vermelhos (id 1 / id 2)
  - posse, chutes, etc.

Com isso montamos, pra cada time, as medias por jogo de:
  gols feitos/sofridos, xG/xGA, escanteios feitos/sofridos e cartoes recebidos.

Endpoints usados:
  GET /web/games/         -> lista de jogos de um periodo (placar + status)
  GET /web/game/stats/    -> estatisticas da partida (xG, escanteios, cartoes)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.forca import EstatisticasTime  # noqa: E402
from dados.jogos import Jogo  # noqa: E402

BASE = "https://webws.365scores.com/web"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.365scores.com/"}
PARAMS_BASE = {
    "appTypeId": 5, "langId": 31,
    "timezoneName": "America/Sao_Paulo", "userCountryId": 21,
}

# IDs das estatisticas no 365scores
STAT_XG = 76
STAT_ESCANTEIOS = 8
STAT_CARTAO_AMARELO = 1
STAT_CARTAO_VERMELHO = 2

# IDs das competicoes no 365scores
COMPETICOES_365 = {
    "copa_mundo": 5930,
    "brasileirao_a": 113,
    "brasileirao_b": 116,
}


def _get(caminho: str, **params) -> dict:
    p = dict(PARAMS_BASE)
    p.update(params)
    r = requests.get(f"{BASE}/{caminho}/", params=p, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def listar_jogos(comp_id: int, d1: str, d2: str) -> list[dict]:
    """Jogos (brutos) de uma competicao entre d1 e d2 (formato DD/MM/AAAA)."""
    d = _get("games", competitions=comp_id, startDate=d1, endDate=d2, showOdds="false")
    return [g for g in d.get("games", []) if g.get("competitionId") == comp_id]


def stats_partida(game_id: int) -> dict[int, dict[int, float]]:
    """
    Estatisticas de uma partida: {competitorId: {stat_id: valor}}.
    Filtra so o que o modelo usa: xG, escanteios e cartoes.
    """
    d = _get("game/stats", games=game_id)
    relevantes = (STAT_XG, STAT_ESCANTEIOS, STAT_CARTAO_AMARELO, STAT_CARTAO_VERMELHO)
    out: dict[int, dict[int, float]] = {}
    for s in d.get("statistics", []):
        cid = s.get("competitorId")
        sid = s.get("id")
        if cid is None or sid not in relevantes:
            continue
        try:
            val = float(str(s.get("value", "0")).replace("%", "").replace(",", "."))
        except ValueError:
            continue
        out.setdefault(cid, {})[sid] = val
    return out


def _finalizado(g: dict) -> bool:
    # No 365scores, jogo encerrado vem com statusGroup == 4 (texto "Fim").
    hc, ac = g.get("homeCompetitor", {}), g.get("awayCompetitor", {})
    return (g.get("statusGroup") in (3, 4)
            and hc.get("score", -1) >= 0 and ac.get("score", -1) >= 0)


def _janelas(d1: str, d2: str, passo_dias: int = 25):
    """Quebra [d1, d2] em sub-janelas de no maximo passo_dias (a API do 365scores
    nao aceita intervalos muito grandes - acima de ~30 dias volta vazio)."""
    from datetime import datetime, timedelta
    ini = datetime.strptime(d1, "%d/%m/%Y")
    fim = datetime.strptime(d2, "%d/%m/%Y")
    atual = ini
    while atual <= fim:
        prox = min(atual + timedelta(days=passo_dias - 1), fim)
        yield atual.strftime("%d/%m/%Y"), prox.strftime("%d/%m/%Y")
        atual = prox + timedelta(days=1)


def coletar_estatisticas(comp_id: int, d1: str, d2: str,
                         max_jogos: int = 120, pausa: float = 0.15
                         ) -> dict[str, EstatisticasTime]:
    """
    Agrega, por time, as medias por jogo (gols, xG, escanteios) a partir dos
    jogos JA FINALIZADOS no periodo. Faz 1 chamada de stats por jogo.
    """
    # coleta em blocos de 25 dias e remove duplicatas por id de jogo
    vistos: dict[int, dict] = {}
    for ja, jb in _janelas(d1, d2):
        for g in listar_jogos(comp_id, ja, jb):
            if _finalizado(g):
                vistos[g["id"]] = g
    jogos = sorted(vistos.values(), key=lambda g: g.get("startTime", ""))[-max_jogos:]

    acc: dict[str, dict] = {}

    def garante(nome):
        acc.setdefault(nome, dict(jogos=0, gf=0.0, gs=0.0, xg=0.0, xga=0.0,
                                  ef=0.0, es=0.0, xg_n=0, esc_n=0,
                                  cart=0.0, cart_n=0))
        return acc[nome]

    def cartoes_de(st_time):
        am = st_time.get(STAT_CARTAO_AMARELO)
        ver = st_time.get(STAT_CARTAO_VERMELHO)
        if am is None and ver is None:
            return None
        return (am or 0) + (ver or 0)

    for i, g in enumerate(jogos):
        hc, ac = g["homeCompetitor"], g["awayCompetitor"]
        nome_h, nome_a = hc["name"], ac["name"]
        gh, ga = float(hc["score"]), float(ac["score"])

        try:
            st = stats_partida(g["id"])
        except Exception:
            st = {}
        time.sleep(pausa)

        xg_h = st.get(hc["id"], {}).get(STAT_XG)
        xg_a = st.get(ac["id"], {}).get(STAT_XG)
        ef_h = st.get(hc["id"], {}).get(STAT_ESCANTEIOS)
        ef_a = st.get(ac["id"], {}).get(STAT_ESCANTEIOS)

        H, A = garante(nome_h), garante(nome_a)
        H["jogos"] += 1; A["jogos"] += 1
        H["gf"] += gh; H["gs"] += ga
        A["gf"] += ga; A["gs"] += gh
        if xg_h is not None and xg_a is not None:
            H["xg"] += xg_h; H["xga"] += xg_a; H["xg_n"] += 1
            A["xg"] += xg_a; A["xga"] += xg_h; A["xg_n"] += 1
        if ef_h is not None and ef_a is not None:
            H["ef"] += ef_h; H["es"] += ef_a; H["esc_n"] += 1
            A["ef"] += ef_a; A["es"] += ef_h; A["esc_n"] += 1

        cart_h = cartoes_de(st.get(hc["id"], {}))
        cart_a = cartoes_de(st.get(ac["id"], {}))
        if cart_h is not None:
            H["cart"] += cart_h; H["cart_n"] += 1
        if cart_a is not None:
            A["cart"] += cart_a; A["cart_n"] += 1

    times: dict[str, EstatisticasTime] = {}
    for nome, a in acc.items():
        j = a["jogos"]
        if j == 0:
            continue
        times[nome] = EstatisticasTime(
            nome=nome, jogos=j,
            gols_feitos_por_jogo=a["gf"] / j,
            gols_sofridos_por_jogo=a["gs"] / j,
            xg_por_jogo=(a["xg"] / a["xg_n"]) if a["xg_n"] else None,
            xga_por_jogo=(a["xga"] / a["xg_n"]) if a["xg_n"] else None,
            escanteios_feitos_por_jogo=(a["ef"] / a["esc_n"]) if a["esc_n"] else None,
            escanteios_sofridos_por_jogo=(a["es"] / a["esc_n"]) if a["esc_n"] else None,
            cartoes_por_jogo=(a["cart"] / a["cart_n"]) if a["cart_n"] else None,
        )
    return times


def coletar_jogos_futuros(comp_id: int, liga_key: str, d1: str, d2: str) -> list[Jogo]:
    """Proximos jogos (ainda nao finalizados) da competicao no periodo."""
    from datetime import datetime
    jogos = []
    for g in listar_jogos(comp_id, d1, d2):
        if _finalizado(g):
            continue
        try:
            dt = datetime.fromisoformat(g["startTime"].replace("Z", "+00:00"))
            data = dt.strftime("%Y-%m-%d")
            hora = dt.strftime("%H:%M")
        except Exception:
            data, hora = g.get("startTime", "")[:10], ""
        jogos.append(Jogo(
            liga_key=liga_key, data=data, hora=hora,
            mandante=g["homeCompetitor"]["name"],
            visitante=g["awayCompetitor"]["name"],
            rodada=g.get("roundName", ""),
        ))
    return jogos
