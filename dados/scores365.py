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
from datetime import datetime, timezone
from math import exp
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

import json  # noqa: E402

from config import PASTA_CACHE  # noqa: E402
from motor.forca import EstatisticasTime  # noqa: E402
from dados.jogos import Jogo  # noqa: E402

_CACHE_STATS = PASTA_CACHE / "stats365"

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


def stats_partida(game_id: int, usar_cache: bool = True) -> dict[int, dict[int, float]]:
    """
    Estatisticas de uma partida: {competitorId: {stat_id: valor}}.
    Filtra so o que o modelo usa: xG, escanteios e cartoes.
    Jogos finalizados nao mudam, entao cacheamos em disco (cache/stats365/<id>.json)
    -> backtest e atualizacao diaria nao refazem chamadas.
    """
    cache_file = _CACHE_STATS / f"{game_id}.json"
    if usar_cache and cache_file.exists():
        try:
            raw = json.loads(cache_file.read_text(encoding="utf-8"))
            return {int(k): {int(kk): vv for kk, vv in v.items()} for k, v in raw.items()}
        except (ValueError, OSError):
            pass

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

    if out:  # so cacheia partida com stats (finalizada)
        try:
            _CACHE_STATS.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({str(k): {str(kk): vv for kk, vv in v.items()} for k, v in out.items()}),
                encoding="utf-8")
        except OSError:
            pass
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


# Decaimento temporal: jogo de 100 dias atrás vale exp(-0.007*100) ≈ 50%
_LAMBDA_DECAY = 0.007
_AGORA_UTC = datetime.now(timezone.utc)


def _peso_temporal(start_time_str: str) -> float:
    """Peso de decaimento exponencial baseado na data do jogo."""
    try:
        dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        dias = max(0, (_AGORA_UTC - dt).days)
        return exp(-_LAMBDA_DECAY * dias)
    except Exception:
        return 0.5  # peso neutro se data inválida


def coletar_jogos_brutos_srs(
    comp_id: int, d1: str, d2: str,
    max_jogos: int = 120,
) -> list[tuple[str, str, float, float, float]]:
    """
    Retorna lista de (mandante, visitante, gm, gv, peso_decay) para o SRS.
    Não faz chamadas de stats por jogo — apenas listar_jogos (rápido).
    """
    vistos: dict[int, dict] = {}
    for ja, jb in _janelas(d1, d2):
        for g in listar_jogos(comp_id, ja, jb):
            if _finalizado(g):
                vistos[g["id"]] = g
    jogos = sorted(vistos.values(), key=lambda g: g.get("startTime", ""))[-max_jogos:]

    resultado = []
    for g in jogos:
        hc, ac = g["homeCompetitor"], g["awayCompetitor"]
        gh = float(hc.get("score") or 0)
        ga = float(ac.get("score") or 0)
        peso = _peso_temporal(g.get("startTime", ""))
        resultado.append((hc["name"], ac["name"], gh, ga, peso))
    return resultado


def coletar_estatisticas(comp_id: int, d1: str, d2: str,
                         max_jogos: int = 120, pausa: float = 0.15
                         ) -> dict[str, EstatisticasTime]:
    """
    Agrega, por time, as medias por jogo (gols, xG, escanteios) a partir dos
    jogos JA FINALIZADOS no periodo. Faz 1 chamada de stats por jogo.
    Usa decaimento temporal: jogos recentes pesam mais (exp(-λ·dias)).
    Rastreia splits casa/fora para vantagem de casa por time.
    """
    vistos: dict[int, dict] = {}
    for ja, jb in _janelas(d1, d2):
        for g in listar_jogos(comp_id, ja, jb):
            if _finalizado(g):
                vistos[g["id"]] = g
    jogos = sorted(vistos.values(), key=lambda g: g.get("startTime", ""))[-max_jogos:]

    acc: dict[str, dict] = {}

    def garante(nome):
        acc.setdefault(nome, dict(
            jogos=0.0, gf=0.0, gs=0.0, xg=0.0, xga=0.0,
            ef=0.0, es=0.0, xg_n=0.0, esc_n=0.0,
            cart=0.0, cart_n=0.0,
            # splits casa / fora
            j_casa=0.0, gf_casa=0.0, gs_casa=0.0,
            j_fora=0.0, gf_fora=0.0, gs_fora=0.0,
        ))
        return acc[nome]

    def cartoes_de(st_time):
        am = st_time.get(STAT_CARTAO_AMARELO)
        ver = st_time.get(STAT_CARTAO_VERMELHO)
        if am is None and ver is None:
            return None
        return (am or 0) + (ver or 0)

    for g in jogos:
        hc, ac = g["homeCompetitor"], g["awayCompetitor"]
        nome_h, nome_a = hc["name"], ac["name"]
        gh, ga = float(hc["score"]), float(ac["score"])
        peso = _peso_temporal(g.get("startTime", ""))

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

        # Estatísticas globais ponderadas por tempo
        H["jogos"] += peso;   A["jogos"] += peso
        H["gf"] += gh * peso; H["gs"] += ga * peso
        A["gf"] += ga * peso; A["gs"] += gh * peso

        # Splits casa / fora
        H["j_casa"]  += peso; H["gf_casa"] += gh * peso; H["gs_casa"] += ga * peso
        A["j_fora"]  += peso; A["gf_fora"] += ga * peso; A["gs_fora"] += gh * peso

        if xg_h is not None and xg_a is not None:
            H["xg"] += xg_h * peso; H["xga"] += xg_a * peso; H["xg_n"] += peso
            A["xg"] += xg_a * peso; A["xga"] += xg_h * peso; A["xg_n"] += peso
        if ef_h is not None and ef_a is not None:
            H["ef"] += ef_h * peso; H["es"] += ef_a * peso; H["esc_n"] += peso
            A["ef"] += ef_a * peso; A["es"] += ef_h * peso; A["esc_n"] += peso

        cart_h = cartoes_de(st.get(hc["id"], {}))
        cart_a = cartoes_de(st.get(ac["id"], {}))
        if cart_h is not None:
            H["cart"] += cart_h * peso; H["cart_n"] += peso
        if cart_a is not None:
            A["cart"] += cart_a * peso; A["cart_n"] += peso

    times: dict[str, EstatisticasTime] = {}
    for nome, a in acc.items():
        j = a["jogos"]
        if j < 0.1:
            continue

        # Casa / fora: só preenche se tiver dados suficientes
        gf_casa = a["gf_casa"] / a["j_casa"] if a["j_casa"] >= 0.5 else None
        gs_casa = a["gs_casa"] / a["j_casa"] if a["j_casa"] >= 0.5 else None
        gf_fora = a["gf_fora"] / a["j_fora"] if a["j_fora"] >= 0.5 else None
        gs_fora = a["gs_fora"] / a["j_fora"] if a["j_fora"] >= 0.5 else None

        times[nome] = EstatisticasTime(
            nome=nome,
            jogos=round(j),
            gols_feitos_por_jogo=a["gf"] / j,
            gols_sofridos_por_jogo=a["gs"] / j,
            xg_por_jogo=(a["xg"] / a["xg_n"]) if a["xg_n"] > 0.1 else None,
            xga_por_jogo=(a["xga"] / a["xg_n"]) if a["xg_n"] > 0.1 else None,
            escanteios_feitos_por_jogo=(a["ef"] / a["esc_n"]) if a["esc_n"] > 0.1 else None,
            escanteios_sofridos_por_jogo=(a["es"] / a["esc_n"]) if a["esc_n"] > 0.1 else None,
            cartoes_por_jogo=(a["cart"] / a["cart_n"]) if a["cart_n"] > 0.1 else None,
            gols_feitos_casa_por_jogo=gf_casa,
            gols_sofridos_casa_por_jogo=gs_casa,
            jogos_casa=round(a["j_casa"]),
            gols_feitos_fora_por_jogo=gf_fora,
            gols_sofridos_fora_por_jogo=gs_fora,
            jogos_fora=round(a["j_fora"]),
        )
    return times


def medias_liga(comp_id: int, d1: str, d2: str) -> tuple[float | None, float | None]:
    """
    Média REAL de gols mandante e visitante da competição no período.
    Usa só listar_jogos (rápido, sem chamadas de stats por partida).
    Retorna (None, None) se não houver jogos finalizados.
    """
    vistos: dict[int, dict] = {}
    for ja, jb in _janelas(d1, d2):
        for g in listar_jogos(comp_id, ja, jb):
            if _finalizado(g):
                vistos[g["id"]] = g
    jogos = list(vistos.values())
    if not jogos:
        return None, None
    gm = sum(float(g["homeCompetitor"]["score"]) for g in jogos) / len(jogos)
    gv = sum(float(g["awayCompetitor"]["score"]) for g in jogos) / len(jogos)
    return round(gm, 3), round(gv, 3)


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
