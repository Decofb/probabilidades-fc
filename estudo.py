"""
ESTUDO  ->  raio-x dos jogos JA DISPUTADOS em cada competicao.

Puxa todos os jogos finalizados (via cache do 365scores) e calcula o "ambiente"
de cada liga: gols, vantagem de casa, over/under, ambas marcam, escanteios,
cartoes, placares mais comuns. Serve de leitura do terreno e valida os
parametros do Cerebro contra a realidade.

Roda:  python estudo.py            (padrao ~210 dias = temporada toda + Copa)
       python estudo.py --dias 240
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timedelta

from config import LIGAS, parametros_da_liga
from dados.scores365 import COMPETICOES_365
from backtest import coletar_registros

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def pct(parte, total):
    return (parte / total * 100) if total else 0.0


def estudar(reg: list[dict]) -> dict:
    n = len(reg)
    if n == 0:
        return {"n": 0}
    gh = [r["gh"] for r in reg]
    ga = [r["ga"] for r in reg]
    totais = [a + b for a, b in zip(gh, ga)]

    placares = Counter((int(a), int(b)) for a, b in zip(gh, ga))
    goleada = max(reg, key=lambda r: abs(r["gh"] - r["ga"]))

    corners = [r["cf_h"] + r["cf_a"] for r in reg if r["cf_h"] is not None and r["cf_a"] is not None]
    cards = [r["ca_h"] + r["ca_a"] for r in reg if r["ca_h"] is not None and r["ca_a"] is not None]
    xgs = [r["xg_h"] + r["xg_a"] for r in reg if r["xg_h"] is not None and r["xg_a"] is not None]

    return {
        "n": n,
        "gols_jogo": sum(totais) / n,
        "gols_casa": sum(gh) / n, "gols_fora": sum(ga) / n,
        "vit_casa": pct(sum(a > b for a, b in zip(gh, ga)), n),
        "empate": pct(sum(a == b for a, b in zip(gh, ga)), n),
        "vit_fora": pct(sum(a < b for a, b in zip(gh, ga)), n),
        "o05": pct(sum(t >= 1 for t in totais), n),
        "o15": pct(sum(t >= 2 for t in totais), n),
        "o25": pct(sum(t >= 3 for t in totais), n),
        "o35": pct(sum(t >= 4 for t in totais), n),
        "btts": pct(sum(a >= 1 and b >= 1 for a, b in zip(gh, ga)), n),
        "xg_jogo": (sum(xgs) / len(xgs)) if xgs else None,
        "esc_jogo": (sum(corners) / len(corners)) if corners else None,
        "esc_o95": pct(sum(c > 9.5 for c in corners), len(corners)) if corners else None,
        "cart_jogo": (sum(cards) / len(cards)) if cards else None,
        "cart_o45": pct(sum(c > 4.5 for c in cards), len(cards)) if cards else None,
        "placares": placares.most_common(5),
        "goleada": (goleada["home"], int(goleada["gh"]), int(goleada["ga"]), goleada["away"], goleada["data"]),
    }


def relatar(nome, s, liga):
    print(f"\n{'='*54}\n{nome.upper()}  —  {s['n']} jogos disputados\n{'='*54}")
    if s["n"] == 0:
        print("  (sem jogos no periodo)")
        return
    print(f"  Gols por jogo ........ {s['gols_jogo']:.2f}"
          + (f"   (xG médio {s['xg_jogo']:.2f})" if s["xg_jogo"] else ""))
    print(f"  Gols mandante/visit .. {s['gols_casa']:.2f} / {s['gols_fora']:.2f}"
          f"   (modelo usa {liga.media_gols_mandante:.2f}/{liga.media_gols_visitante:.2f}"
          f"{' · campo neutro' if liga.campo_neutro else ''})")
    print(f"  Resultado ............ casa {s['vit_casa']:.0f}%  |  empate {s['empate']:.0f}%  |  fora {s['vit_fora']:.0f}%")
    print(f"  Over .................  0.5: {s['o05']:.0f}%   1.5: {s['o15']:.0f}%   "
          f"2.5: {s['o25']:.0f}%   3.5: {s['o35']:.0f}%")
    print(f"  Ambas marcam ......... {s['btts']:.0f}%")
    if s["esc_jogo"]:
        print(f"  Escanteios/jogo ...... {s['esc_jogo']:.1f}   (over 9.5 em {s['esc_o95']:.0f}%)")
    if s["cart_jogo"]:
        print(f"  Cartões/jogo ......... {s['cart_jogo']:.1f}   (over 4.5 em {s['cart_o45']:.0f}%)")
    placs = "  ".join(f"{a}-{b} ({c})" for (a, b), c in s["placares"])
    print(f"  Placares + comuns .... {placs}")
    g = s["goleada"]
    print(f"  Maior goleada ........ {g[0]} {g[1]}-{g[2]} {g[3]}  ({g[4]})")


def main(dias=210):
    fim = datetime.now()
    d2, d1 = fim.strftime("%d/%m/%Y"), (fim - timedelta(days=dias)).strftime("%d/%m/%Y")
    print(f"\n### ESTUDO DOS JOGOS DISPUTADOS ({d1} a {d2}) ###")
    for liga_key, comp in COMPETICOES_365.items():
        print(f"\n...coletando {LIGAS[liga_key]['nome']}", flush=True)
        reg = coletar_registros(comp, d1, d2)
        relatar(LIGAS[liga_key]["nome"], estudar(reg), parametros_da_liga(liga_key))
    print()


if __name__ == "__main__":
    dias = 210
    if "--dias" in sys.argv:
        dias = int(sys.argv[sys.argv.index("--dias") + 1])
    main(dias=dias)
