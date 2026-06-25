"""
OTIMIZAR.PY  ->  acha, por EVIDENCIA, os melhores parametros do modelo.

Reaproveita o backtest (dados em cache) e varre:
  - gols: fator de nivel de gols x rho (Dixon-Coles), minimizando o log-loss
          combinado de 1X2 + Over 1.5 + Over 2.5 + Ambas Marcam.
  - escanteios/cartoes: estima a dispersao empirica e testa a Binomial Negativa
          contra o baseline (so vale a pena se ganhar do baseline).

Roda:  python otimizar.py
"""

from __future__ import annotations

import dataclasses
import sys
from datetime import datetime, timedelta

from config import LIGAS, parametros_da_liga
from dados.scores365 import COMPETICOES_365
from backtest import coletar_registros, construir_historico, stats_antes, Binario, Tripla
from motor.forca import gols_esperados, escanteios_esperados, cartoes_esperados
from motor.poisson import calcular_mercados

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DIAS = 90


def carregar(dias=DIAS):
    fim = datetime.now()
    d2, d1 = fim.strftime("%d/%m/%Y"), (fim - timedelta(days=dias)).strftime("%d/%m/%Y")
    dados = {}
    for liga_key, comp in COMPETICOES_365.items():
        reg = coletar_registros(comp, d1, d2)
        dados[liga_key] = (reg, construir_historico(reg))
    return dados


def avaliar(dados, fator_gols=1.0, rho=-0.06, disp_esc=None, disp_cart=None):
    x12, o15, o25, btts = Tripla(), Binario("o15"), Binario("o25"), Binario("btts")
    esc, cart = Binario("esc"), Binario("cart")
    for liga_key, (reg, hist) in dados.items():
        base = parametros_da_liga(liga_key)
        liga = dataclasses.replace(
            base, media_gols_mandante=base.media_gols_mandante * fator_gols,
            media_gols_visitante=base.media_gols_visitante * fator_gols)
        for r in reg:
            tm = stats_antes(hist, r["home"], r["data"])
            tv = stats_antes(hist, r["away"], r["data"])
            if not tm or not tv:
                continue
            lam_m, lam_v = gols_esperados(tm, tv, liga)
            m = calcular_mercados(
                lam_m, lam_v,
                lam_escanteios=escanteios_esperados(tm, tv, liga),
                lam_cartoes=cartoes_esperados(tm, tv, liga),
                rho=rho, disp_escanteios=disp_esc, disp_cartoes=disp_cart)
            gh, ga = r["gh"], r["ga"]
            tot = gh + ga
            res = 0 if gh > ga else (1 if gh == ga else 2)
            x12.add((m.vitoria_mandante, m.empate, m.vitoria_visitante), res)
            o15.add(m.over_15, tot >= 2)
            o25.add(m.over_25, tot >= 3)
            btts.add(m.ambas_marcam, gh >= 1 and ga >= 1)
            if m.escanteios and r["cf_h"] is not None and r["cf_a"] is not None:
                esc.add(m.escanteios["over_9_5"], (r["cf_h"] + r["cf_a"]) > 9.5)
            if m.cartoes and r["ca_h"] is not None and r["ca_a"] is not None:
                cart.add(m.cartoes["over_4_5"], (r["ca_h"] + r["ca_a"]) > 4.5)
    return dict(x12=x12, o15=o15, o25=o25, btts=btts, esc=esc, cart=cart)


def logloss_gols(c):
    return (c["x12"].resumo()["logloss"] + c["o15"].resumo()["logloss"]
            + c["o25"].resumo()["logloss"] + c["btts"].resumo()["logloss"])


def dispersao_empirica(dados, campo_h, campo_a):
    """r da Binomial Negativa estimado dos totais reais: r = mu^2/(var-mu)."""
    totais = []
    for _, (reg, _) in dados.items():
        for r in reg:
            a, b = r[campo_h], r[campo_a]
            if a is not None and b is not None:
                totais.append(a + b)
    n = len(totais)
    mu = sum(totais) / n
    var = sum((t - mu) ** 2 for t in totais) / (n - 1)
    r = mu * mu / (var - mu) if var > mu else 50.0
    return mu, var, max(1.0, min(r, 50.0)), n


def main():
    print(f"\n=== OTIMIZACAO (backtest {DIAS}d, dados em cache) ===\n")
    dados = carregar()

    base = avaliar(dados)  # parametros atuais
    ll0 = logloss_gols(base)
    print(f"Atual (fator=1.00, rho=-0.06):  logloss_gols={ll0:.4f}")
    print(f"   Over2.5: prev medio {sum(base['o25'].ps)/len(base['o25'].ps):.0%} | real {base['o25'].resumo()['base']:.0%}")
    print(f"   BTTS:    prev medio {sum(base['btts'].ps)/len(base['btts'].ps):.0%} | real {base['btts'].resumo()['base']:.0%}\n")

    print("Varredura gols (fator x rho) -> logloss combinado:")
    melhor = (ll0, 1.0, -0.06)
    for fator in (1.0, 1.05, 1.10, 1.15):
        linha = []
        for rho in (0.0, -0.03, -0.06):
            c = avaliar(dados, fator_gols=fator, rho=rho)
            ll = logloss_gols(c)
            linha.append(f"rho={rho:+.2f}:{ll:.4f}")
            if ll < melhor[0]:
                melhor = (ll, fator, rho)
        print(f"  fator={fator:.2f}  " + "  ".join(linha))
    print(f"\n>>> MELHOR gols: fator={melhor[1]:.2f}, rho={melhor[2]:+.2f}  (logloss {melhor[0]:.4f} vs {ll0:.4f})")

    # escanteios e cartoes: dispersao + NB
    print("\nEscanteios/Cartoes — Binomial Negativa vs Poisson:")
    mu_e, var_e, r_e, n_e = dispersao_empirica(dados, "cf_h", "cf_a")
    mu_c, var_c, r_c, n_c = dispersao_empirica(dados, "ca_h", "ca_a")
    print(f"  Escanteios: media {mu_e:.1f}, var {var_e:.1f} -> dispersao r={r_e:.1f} (n={n_e})")
    print(f"  Cartoes:    media {mu_c:.1f}, var {var_c:.1f} -> dispersao r={r_c:.1f} (n={n_c})")

    f, rho = melhor[1], melhor[2]
    com_nb = avaliar(dados, fator_gols=f, rho=rho, disp_esc=r_e, disp_cart=r_c)
    sem_nb = avaliar(dados, fator_gols=f, rho=rho)
    for nome, k in (("ESCANTEIOS +9.5", "esc"), ("CARTOES +4.5", "cart")):
        sp, sn = sem_nb[k].resumo(), com_nb[k].resumo()
        print(f"\n  {nome}: baseline Brier={sn['brier_base']:.3f}")
        print(f"     Poisson  Brier={sp['brier']:.3f}  {'(ganha)' if sp['brier']<sp['brier_base'] else '(perde)'}")
        print(f"     Neg.Bin. Brier={sn['brier']:.3f}  {'(ganha)' if sn['brier']<sn['brier_base'] else '(perde)'}")

    print("\n>>> RECOMENDACAO:")
    print(f"    gols: fator={f:.2f}, rho={rho:+.2f}")
    print(f"    escanteios: dispersao r={r_e:.1f} | cartoes: dispersao r={r_c:.1f}")
    print("    (aplicar so o que ganhar do baseline; marcar como baixa confianca o que nao ganhar)\n")


if __name__ == "__main__":
    main()
