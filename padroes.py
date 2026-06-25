"""
PADRÕES POR EQUIPE  ->  o "DNA" de cada time na temporada.

Para cada equipe: ataque/defesa (gols e xG), over/under, ambas marcam, clean
sheets, eficiência (gols vs xG), disciplina e mando casa/fora. E auto-destaca os
PADRÕES que fogem da média da liga — onde mora a leitura de valor.

Roda:  python padroes.py            (Série A e B)
       python padroes.py --liga brasileirao_b
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime

from config import LIGAS, janela_liga
from dados.scores365 import COMPETICOES_365
from backtest import coletar_registros
from estudo import estudar

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def perfis_detalhados(reg: list[dict]) -> dict:
    t = defaultdict(lambda: dict(j=0, V=0, E=0, D=0, gf=0.0, ga=0.0, xgf=0.0, xga=0.0, xn=0,
                                 marcou=0, cs=0, over25=0, btts=0, cards=0.0, cn=0,
                                 jc=0, vc=0, jf=0, vf=0))

    def add(nome, gf, ga, xgf, xga, card, casa):
        d = t[nome]
        d["j"] += 1
        d["gf"] += gf
        d["ga"] += ga
        d["V"] += 1 if gf > ga else 0
        d["E"] += 1 if gf == ga else 0
        d["D"] += 1 if gf < ga else 0
        d["marcou"] += 1 if gf >= 1 else 0
        d["cs"] += 1 if ga == 0 else 0
        d["over25"] += 1 if gf + ga >= 3 else 0
        d["btts"] += 1 if gf >= 1 and ga >= 1 else 0
        if xgf is not None and xga is not None:
            d["xgf"] += xgf
            d["xga"] += xga
            d["xn"] += 1
        if card is not None:
            d["cards"] += card
            d["cn"] += 1
        if casa:
            d["jc"] += 1
            d["vc"] += 1 if gf > ga else 0
        else:
            d["jf"] += 1
            d["vf"] += 1 if gf > ga else 0

    for r in reg:
        add(r["home"], r["gh"], r["ga"], r["xg_h"], r["xg_a"], r["ca_h"], True)
        add(r["away"], r["ga"], r["gh"], r["xg_a"], r["xg_h"], r["ca_a"], False)
    return t


def padroes(d, avg) -> list[str]:
    j = d["j"]
    o25 = d["over25"] / j
    btts = d["btts"] / j
    cs = d["cs"] / j
    sem_marcar = (j - d["marcou"]) / j
    draw = d["E"] / j
    xgdif = (d["gf"] / j - d["xgf"] / d["xn"]) if d["xn"] else 0.0
    cart = d["cards"] / d["cn"] if d["cn"] else 0.0
    cart_liga = (avg.get("cart_jogo") or 5.0) / 2
    f = []
    if o25 >= avg["o25"] / 100 + 0.15:
        f.append(f"🔥 Over ({o25:.0%} dos jogos)")
    if o25 <= avg["o25"] / 100 - 0.15:
        f.append(f"🧱 Under ({1 - o25:.0%})")
    if btts >= avg["btts"] / 100 + 0.15:
        f.append(f"🤝 Ambas marcam ({btts:.0%})")
    if cs >= 0.38:
        f.append(f"🔒 Muralha (CS {cs:.0%})")
    if sem_marcar >= 0.35:
        f.append(f"😶 Apagado ({sem_marcar:.0%} sem marcar)")
    if xgdif <= -0.30:
        f.append(f"🍀 Azarado ({xgdif:+.2f} vs xG)")
    if xgdif >= 0.30:
        f.append(f"🎲 Sortudo ({xgdif:+.2f} vs xG)")
    if draw >= 0.40:
        f.append(f"⚖️ Empata muito ({draw:.0%})")
    if cart >= cart_liga + 0.8:
        f.append(f"🟨 Faltoso ({cart:.1f}/jogo)")
    if d["jc"] >= 3 and d["jf"] >= 3:
        vc, vf = d["vc"] / d["jc"], d["vf"] / d["jf"]
        if vc - vf >= 0.35:
            f.append(f"🏰 Casa-dependente ({vc:.0%} casa / {vf:.0%} fora)")
    return f


def relatar(nome, reg, min_jogos=6):
    avg = estudar(reg)
    t = perfis_detalhados(reg)
    t = {k: v for k, v in t.items() if v["j"] >= min_jogos}
    print(f"\n{'='*60}\n{nome.upper()}  —  padrões de {len(t)} equipes\n{'='*60}")
    for nm, d in sorted(t.items(), key=lambda kv: -(kv[1]["V"] * 3 + kv[1]["E"])):
        j = d["j"]
        xg = f"{d['xgf']/d['xn']:.2f}" if d["xn"] else "-"
        xga = f"{d['xga']/d['xn']:.2f}" if d["xn"] else "-"
        print(f"\n  {nm}  ({j}j: {d['V']}V {d['E']}E {d['D']}D)")
        print(f"    ataque {d['gf']/j:.2f} (xG {xg}) · defesa {d['ga']/j:.2f} (xGA {xga}) · "
              f"over2.5 {d['over25']/j:.0%} · BTTS {d['btts']/j:.0%} · CS {d['cs']/j:.0%}")
        pads = padroes(d, avg)
        if pads:
            print(f"    PADRÕES: {' · '.join(pads)}")


def main(liga=None):
    hoje = datetime.now().date()
    ligas = [liga] if liga else ["brasileirao_a", "brasileirao_b"]
    print(f"\n### PADRÕES POR EQUIPE — TEMPORADA (até {hoje.strftime('%d/%m/%Y')}) ###")
    for lk in ligas:
        d1, d2 = janela_liga(lk, 210, hoje)
        print(f"\n...coletando {LIGAS[lk]['nome']} (desde {d1})", flush=True)
        relatar(LIGAS[lk]["nome"], coletar_registros(COMPETICOES_365[lk], d1, d2))
    print()


if __name__ == "__main__":
    liga = None
    if "--liga" in sys.argv:
        liga = sys.argv[sys.argv.index("--liga") + 1]
    main(liga=liga)
