"""
RELATORIO VIVO  ->  calibracao das previsoes REAIS ja conferidas (forward).

Diferente do backtest (que reconstroi o passado), aqui medimos as previsoes que
o modelo de fato fez, dia a dia, contra o resultado que aconteceu depois.
Quanto mais rodadas, mais confiavel.

Roda:  python relatorio.py
"""

from __future__ import annotations

import sys

from dados.registro import carregar
from backtest import Binario, Tripla

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    rows = [r for r in carregar() if r.get("status") == "conferido"]
    print(f"\n=== RELATORIO VIVO ({len(rows)} jogos conferidos) ===\n")
    if len(rows) < 10:
        print("Poucos jogos conferidos ainda. O log enche sozinho a cada rodada —")
        print("rode de novo daqui a alguns dias para uma leitura confiavel.\n")
        if not rows:
            return

    x12 = Tripla()
    o05, o15, o25 = Binario("+0.5 gols"), Binario("+1.5 gols"), Binario("+2.5 gols")
    btts = Binario("Ambas marcam")
    esc, cart = Binario("+9.5 escanteios"), Binario("+4.5 cartões")

    for r in rows:
        gm, gv = _f(r["gm"]), _f(r["gv"])
        if gm is None or gv is None:
            continue
        tot = gm + gv
        res = 0 if gm > gv else (1 if gm == gv else 2)
        p1, px, p2 = _f(r["p1"]), _f(r["px"]), _f(r["p2"])
        if None not in (p1, px, p2):
            x12.add((p1, px, p2), res)
        for col, p, y in ((o05, _f(r["po05"]), tot >= 1), (o15, _f(r["po15"]), tot >= 2),
                          (o25, _f(r["po25"]), tot >= 3), (btts, _f(r["pbtts"]), gm >= 1 and gv >= 1)):
            if p is not None:
                col.add(p, y)
        corners, cards = _f(r["corners"]), _f(r["cards"])
        if _f(r["pesc95"]) is not None and corners is not None:
            esc.add(_f(r["pesc95"]), corners > 9.5)
        if _f(r["pcart45"]) is not None and cards is not None:
            cart.add(_f(r["pcart45"]), cards > 4.5)

    rx = x12.resumo()
    if rx:
        print("== RESULTADO (1X2) ==")
        print(f"  n={rx['n']}  Brier={rx['brier']:.3f} (base {rx['brier_base']:.3f})  "
              f"LogLoss={rx['logloss']:.3f} (base {rx['ll_base']:.3f})")

    for col in (o05, o15, o25, btts, esc, cart):
        s = col.resumo()
        if not s:
            continue
        venc = "(melhor que baseline)" if s["logloss"] < s["ll_base"] else "(nao ganha do baseline)"
        print(f"\n== {col.nome.upper()} ==")
        print(f"  n={s['n']}  taxa real={s['base']:.0%}  Brier={s['brier']:.3f} "
              f"(base {s['brier_base']:.3f})  {venc}")
        for faixa, nb, mp, my in col.calibracao():
            nota = "subestima" if my > mp + 0.05 else ("superestima" if my < mp - 0.05 else "ok")
            print(f"  {faixa:>10} {nb:>5} jogos  prev {mp:>4.0%}  real {my:>4.0%}  {nota}")
    print()


if __name__ == "__main__":
    main()
