"""
ESTUDO POR TIME  ->  relatorio de scout: perfil de cada time e rankings uteis.

O recorte que parametro nenhum entrega: quem ataca/defende melhor (por xG),
quem e "azarado" (marca menos que o xG -> tende a melhorar = value) ou "sortudo"
(marca mais que o xG -> tende a cair), quem joga over, quem e ferrolho, quem
toma/faz mais cartao. Tudo dos jogos JA disputados.

Roda:  python estudo_times.py            (Série A e B; Copa tem poucos jogos/time)
       python estudo_times.py --dias 240
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta

from config import LIGAS
from dados.scores365 import COMPETICOES_365
from backtest import coletar_registros

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def perfis(reg: list[dict]) -> dict:
    t = defaultdict(lambda: dict(j=0, gf=0.0, ga=0.0, xgf=0.0, xga=0.0, xn=0,
                                 tot=0.0, btts=0, over25=0, cards=0.0, cn=0,
                                 corn=0.0, on=0, vc=0, jc=0, vf=0, jf=0))

    def add(nome, gf, ga, xgf, xga, total, card, corn, casa, venceu):
        d = t[nome]
        d["j"] += 1
        d["gf"] += gf
        d["ga"] += ga
        d["tot"] += total
        d["btts"] += 1 if (gf >= 1 and ga >= 1) else 0
        d["over25"] += 1 if total >= 3 else 0
        if xgf is not None and xga is not None:
            d["xgf"] += xgf
            d["xga"] += xga
            d["xn"] += 1
        if card is not None:
            d["cards"] += card
            d["cn"] += 1
        if corn is not None:
            d["corn"] += corn
            d["on"] += 1
        if casa:
            d["jc"] += 1
            d["vc"] += 1 if venceu else 0
        else:
            d["jf"] += 1
            d["vf"] += 1 if venceu else 0

    for r in reg:
        tot = r["gh"] + r["ga"]
        add(r["home"], r["gh"], r["ga"], r["xg_h"], r["xg_a"], tot, r["ca_h"], r["cf_h"], True, r["gh"] > r["ga"])
        add(r["away"], r["ga"], r["gh"], r["xg_a"], r["xg_h"], tot, r["ca_a"], r["cf_a"], False, r["ga"] > r["gh"])
    return t


def rankings(reg: list[dict], min_jogos=6) -> dict:
    """Mesmos recortes do scout, mas como DADOS (para o site Tendencias)."""
    t = perfis(reg)
    t = {k: v for k, v in t.items() if v["j"] >= min_jogos}
    if not t:
        return {}

    def xg_dif(d):
        return (d["gf"] / d["j"] - d["xgf"] / d["xn"]) if d["xn"] else 0.0

    def pj(d, c):
        return d[c] / d["j"]

    return {
        "ataque": sorted(((n, d["xgf"]/d["xn"]) for n, d in t.items() if d["xn"]), key=lambda x: -x[1])[:5],
        "defesa": sorted(((n, d["xga"]/d["xn"]) for n, d in t.items() if d["xn"]), key=lambda x: x[1])[:5],
        "azarados": sorted(((n, xg_dif(d)) for n, d in t.items() if d["xn"]), key=lambda x: x[1])[:5],
        "sortudos": sorted(((n, xg_dif(d)) for n, d in t.items() if d["xn"]), key=lambda x: -x[1])[:5],
        "over": sorted(((n, pj(d, "tot")) for n, d in t.items()), key=lambda x: -x[1])[:5],
        "ferrolho": sorted(((n, pj(d, "tot")) for n, d in t.items()), key=lambda x: x[1])[:5],
        "cartoes": sorted(((n, d["cards"]/d["cn"]) for n, d in t.items() if d["cn"]), key=lambda x: -x[1])[:5],
        "casa": sorted(((n, d["vc"]/d["jc"]) for n, d in t.items() if d["jc"] >= 3), key=lambda x: -x[1])[:5],
    }


def sequencias(reg: list[dict], min_jogos=5) -> dict:
    """Sequências atuais (a partir do último jogo): invencibilidade, vitórias,
    marcando, sem sofrer, over 2.5 e BTTS em série. Top times por cada uma."""
    jogos = defaultdict(list)  # nome -> [(data, res, marcou, sofreu, over, btts)]
    for r in reg:
        tot = r["gh"] + r["ga"]
        btts = r["gh"] >= 1 and r["ga"] >= 1
        jogos[r["home"]].append((r["data"],
                                 "V" if r["gh"] > r["ga"] else ("E" if r["gh"] == r["ga"] else "D"),
                                 r["gh"] >= 1, r["ga"] >= 1, tot >= 3, btts))
        jogos[r["away"]].append((r["data"],
                                 "V" if r["ga"] > r["gh"] else ("E" if r["ga"] == r["gh"] else "D"),
                                 r["ga"] >= 1, r["gh"] >= 1, tot >= 3, btts))

    def streak(seq, cond):
        c = 0
        for g in reversed(seq):
            if cond(g):
                c += 1
            else:
                break
        return c

    res = {"invicto": [], "vitorias": [], "marcando": [], "clean": [], "over": [], "btts": []}
    for nome, seq in jogos.items():
        if len(seq) < min_jogos:
            continue
        seq = sorted(seq, key=lambda g: g[0])
        res["invicto"].append((nome, streak(seq, lambda g: g[1] != "D")))
        res["vitorias"].append((nome, streak(seq, lambda g: g[1] == "V")))
        res["marcando"].append((nome, streak(seq, lambda g: g[2])))
        res["clean"].append((nome, streak(seq, lambda g: not g[3])))
        res["over"].append((nome, streak(seq, lambda g: g[4])))
        res["btts"].append((nome, streak(seq, lambda g: g[5])))
    # so sequencias >= 2 jogos (1 nao e sequencia)
    return {k: [x for x in sorted(v, key=lambda x: -x[1])[:5] if x[1] >= 2] for k, v in res.items()}


def linha_top(titulo, itens, fmt):
    print(f"  {titulo}")
    for nome, val in itens:
        print(f"     {nome:<22} {fmt(val)}")


def relatar(nome, reg, min_jogos=6):
    t = perfis(reg)
    t = {k: v for k, v in t.items() if v["j"] >= min_jogos}
    print(f"\n{'='*58}\n{nome.upper()}  —  {len(t)} times ({sum(v['j'] for v in t.values())//2} jogos)\n{'='*58}")
    if not t:
        print("  (jogos/time insuficientes)")
        return

    def pj(d, campo):  # por jogo
        return d[campo] / d["j"]

    def xg_dif(d):     # gols - xG (eficiencia/sorte na finalizacao)
        if d["xn"] == 0:
            return 0.0
        return d["gf"] / d["j"] - d["xgf"] / d["xn"]

    linha_top("⚔️  Melhor ataque (xG feito/jogo)",
              sorted(((n, d["xgf"]/d["xn"]) for n, d in t.items() if d["xn"]), key=lambda x: -x[1])[:5],
              lambda v: f"{v:.2f} xG")
    linha_top("🛡️  Melhor defesa (xG sofrido/jogo)",
              sorted(((n, d["xga"]/d["xn"]) for n, d in t.items() if d["xn"]), key=lambda x: x[1])[:5],
              lambda v: f"{v:.2f} xGA")
    linha_top("🍀 Azarados (marcam MENOS que o xG → tendem a subir)",
              sorted(((n, xg_dif(d)) for n, d in t.items() if d["xn"]), key=lambda x: x[1])[:5],
              lambda v: f"{v:+.2f} gols vs xG")
    linha_top("🎲 Sortudos (marcam MAIS que o xG → tendem a cair)",
              sorted(((n, xg_dif(d)) for n, d in t.items() if d["xn"]), key=lambda x: -x[1])[:5],
              lambda v: f"{v:+.2f} gols vs xG")
    linha_top("🔥 Times mais OVER (gols totais nos jogos deles)",
              sorted(((n, pj(d, "tot")) for n, d in t.items()), key=lambda x: -x[1])[:5],
              lambda v: f"{v:.2f} gols/jogo")
    linha_top("🧱 Times mais FERROLHO (menos gols totais)",
              sorted(((n, pj(d, "tot")) for n, d in t.items()), key=lambda x: x[1])[:5],
              lambda v: f"{v:.2f} gols/jogo")
    cartoes = [(n, d["cards"]/d["cn"]) for n, d in t.items() if d["cn"]]
    if cartoes:
        linha_top("🟨 Mais cartões (recebidos/jogo)",
                  sorted(cartoes, key=lambda x: -x[1])[:5], lambda v: f"{v:.1f}/jogo")
    fortalezas = [(n, (d["vc"]/d["jc"], d["vf"]/max(1, d["jf"]))) for n, d in t.items() if d["jc"] >= 3]
    linha_top("🏰 Fortalezas em casa (% vitória casa | fora)",
              sorted(fortalezas, key=lambda x: -x[1][0])[:5],
              lambda v: f"{v[0]:.0%} em casa | {v[1]:.0%} fora")


def main(dias=210):
    fim = datetime.now()
    d2, d1 = fim.strftime("%d/%m/%Y"), (fim - timedelta(days=dias)).strftime("%d/%m/%Y")
    print(f"\n### SCOUT POR TIME ({d1} a {d2}) ###")
    for liga_key in ("brasileirao_a", "brasileirao_b"):
        print(f"\n...coletando {LIGAS[liga_key]['nome']}", flush=True)
        reg = coletar_registros(COMPETICOES_365[liga_key], d1, d2)
        relatar(LIGAS[liga_key]["nome"], reg)
    print()


if __name__ == "__main__":
    dias = 210
    if "--dias" in sys.argv:
        dias = int(sys.argv[sys.argv.index("--dias") + 1])
    main(dias=dias)
