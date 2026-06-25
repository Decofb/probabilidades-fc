"""
PLACAR DO CEREBRO  ->  resumo da performance real (previsoes ja conferidas).

Usado pelo site (rodape "Placar do Cerebro") e como base do alerta de drift.
Tudo a partir do log de previsoes (dados/previsoes_log.csv), forward e honesto.
"""

from __future__ import annotations

from dados.registro import carregar

MIN_PARA_MOSTRAR = 8   # abaixo disso, ainda "coletando"
LIMIAR_DRIFT = 0.02    # Brier do 1X2 acima do baseline + isso -> alerta


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def resumo_cerebro() -> dict:
    """Devolve metricas dos jogos ja conferidos (ou {'n':0} se nao houver)."""
    rows = [r for r in carregar() if r.get("status") == "conferido" and _f(r.get("gm")) is not None]
    n = len(rows)
    if n == 0:
        return {"n": 0}

    # 1X2: o palpite (maior prob) acertou?
    acertos = 0
    o25_prev = o25_real = btts_prev = btts_real = 0.0
    brier_1x2 = 0.0
    for r in rows:
        gm, gv = _f(r["gm"]), _f(r["gv"])
        res = 0 if gm > gv else (1 if gm == gv else 2)
        p = [_f(r["p1"]), _f(r["px"]), _f(r["p2"])]
        if None not in p:
            palpite = p.index(max(p))
            acertos += 1 if palpite == res else 0
            brier_1x2 += sum((p[c] - (1 if c == res else 0)) ** 2 for c in range(3))
        po25, pbtts = _f(r["po25"]), _f(r["pbtts"])
        if po25 is not None:
            o25_prev += po25
            o25_real += 1 if (gm + gv) >= 3 else 0
        if pbtts is not None:
            btts_prev += pbtts
            btts_real += 1 if (gm >= 1 and gv >= 1) else 0

    return {
        "n": n,
        "acerto_1x2": acertos / n,
        "brier_1x2": brier_1x2 / n,
        "o25_prev": o25_prev / n, "o25_real": o25_real / n,
        "btts_prev": btts_prev / n, "btts_real": btts_real / n,
    }


def alerta_drift(min_jogos=20) -> str:
    """
    Vigia a calibração: se o Brier do 1X2 ficar pior que o baseline (prever a
    frequência dos resultados) por mais que LIMIAR_DRIFT, devolve um aviso.
    """
    rows = [r for r in carregar() if r.get("status") == "conferido" and _f(r.get("gm")) is not None]
    n = len(rows)
    if n < min_jogos:
        return ""
    res = []
    brier_modelo = 0.0
    for r in rows:
        gm, gv = _f(r["gm"]), _f(r["gv"])
        y = 0 if gm > gv else (1 if gm == gv else 2)
        res.append(y)
        p = [_f(r["p1"]), _f(r["px"]), _f(r["p2"])]
        if None in p:
            return ""
        brier_modelo += sum((p[c] - (1 if c == y else 0)) ** 2 for c in range(3))
    brier_modelo /= n
    freq = [res.count(c) / n for c in range(3)]
    brier_base = sum(sum((freq[c] - (1 if c == y else 0)) ** 2 for c in range(3)) for y in res) / n
    if brier_modelo > brier_base + LIMIAR_DRIFT:
        return (f"⚠️ ALERTA: a calibração do Cérebro caiu (Brier {brier_modelo:.3f} > "
                f"baseline {brier_base:.3f}). Rode o backtest para reavaliar os parâmetros.")
    return ""


def texto_placar() -> str:
    """Frase curta pro rodape do site."""
    s = resumo_cerebro()
    if s["n"] < MIN_PARA_MOSTRAR:
        falta = MIN_PARA_MOSTRAR - s["n"]
        return f"Placar do Cérebro · coletando as primeiras rodadas ({s['n']} jogos conferidos, faltam ~{falta})"
    return (f"Placar do Cérebro · {s['n']} jogos conferidos · "
            f"acertou o favorito (1X2) em {s['acerto_1x2']:.0%} · "
            f"Over 2.5: previu {s['o25_prev']:.0%}, saiu {s['o25_real']:.0%} · "
            f"Ambas: previu {s['btts_prev']:.0%}, saiu {s['btts_real']:.0%}")


def linha_site() -> str:
    """Linha completa pro rodape: alerta de drift (se houver) + placar."""
    drift = alerta_drift()
    placar = texto_placar()
    return f"{drift}  ·  {placar}" if drift else placar


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(texto_placar())
