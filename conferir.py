"""
CONFERIR  ->  concilia as previsoes pendentes com o resultado real do 365scores.

Chamado automaticamente pelo atualizar.py (online) antes de gerar o site, e
tambem rodavel sozinho:  python conferir.py
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from dados.registro import pendentes, conferir as settle, expirar, id_jogo
from dados.scores365 import (COMPETICOES_365, listar_jogos, stats_partida, _finalizado,
                             _janelas, STAT_ESCANTEIOS,
                             STAT_CARTAO_AMARELO, STAT_CARTAO_VERMELHO)

FUSO_BR = timezone(timedelta(hours=-3))


def conferir_pendentes(hoje=None) -> int:
    """Preenche o resultado real das previsoes cujo jogo ja terminou."""
    if hoje is None:
        hoje = datetime.now(FUSO_BR).date()
    expirar(hoje.isoformat(), dias=10)  # joga fora previsoes de jogos que nunca terminaram
    pend = pendentes(hoje.strftime("%Y-%m-%d"))
    if not pend:
        return 0

    datas = sorted(p["data"] for p in pend)
    d1 = datetime.strptime(datas[0], "%Y-%m-%d").strftime("%d/%m/%Y")
    d2 = datetime.strptime(datas[-1], "%Y-%m-%d").strftime("%d/%m/%Y")

    resultados = {}
    for comp in COMPETICOES_365.values():
        for ja, jb in _janelas(d1, d2):
            for g in listar_jogos(comp, ja, jb):
                if not _finalizado(g):
                    continue
                data = g["startTime"][:10]
                hc, ac = g["homeCompetitor"], g["awayCompetitor"]
                try:
                    st = stats_partida(g["id"])
                except Exception:
                    st = {}
                sh, sa = st.get(hc["id"], {}), st.get(ac["id"], {})

                ce_h, ce_a = sh.get(STAT_ESCANTEIOS), sa.get(STAT_ESCANTEIOS)
                corners = (ce_h + ce_a) if ce_h is not None and ce_a is not None else ""

                def cart(s):
                    am, ve = s.get(STAT_CARTAO_AMARELO), s.get(STAT_CARTAO_VERMELHO)
                    return None if am is None and ve is None else (am or 0) + (ve or 0)
                ca_h, ca_a = cart(sh), cart(sa)
                cards = (ca_h + ca_a) if ca_h is not None and ca_a is not None else ""

                gid = id_jogo(data, hc["name"], ac["name"])
                resultados[gid] = (hc["score"], ac["score"], corners, cards)

    agora = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M")
    return settle(resultados, agora)


if __name__ == "__main__":
    n = conferir_pendentes()
    print(f"Conferidas {n} previsoes com resultado real.")
