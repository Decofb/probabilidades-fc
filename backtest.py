"""
BACKTEST + CALIBRACAO  ->  mede o proprio modelo contra resultados reais.

  python backtest.py            (todas as ligas, ~90 dias)
  python backtest.py --dias 120

Como funciona (walk-forward, SEM look-ahead):
  Para cada jogo ja finalizado, reconstroi a forma dos dois times usando SO os
  jogos anteriores aquela data (mesma janela de 45 dias do modelo ao vivo),
  preve com o modelo atual e compara a probabilidade prevista com o que aconteceu.

Metricas por mercado:
  - Brier score   (quanto menor, melhor; 0 = perfeito)
  - Log-loss      (idem; penaliza confianca errada)
  - vs Baseline   (prever sempre a taxa-base; o modelo TEM que ganhar disso)
  - Curva de calibracao (dos jogos que demos ~70%, quantos sairam?)
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from math import log

from config import LIGAS, parametros_da_liga
from dados.scores365 import (COMPETICOES_365, listar_jogos, stats_partida, _finalizado,
                             _janelas, STAT_XG, STAT_ESCANTEIOS,
                             STAT_CARTAO_AMARELO, STAT_CARTAO_VERMELHO)
from motor.forca import (EstatisticasTime, gols_esperados,
                         escanteios_esperados, cartoes_esperados)
from motor.poisson import calcular_mercados

try:  # console do Windows nem sempre e UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LOOKBACK_DIAS = 45   # mesma janela do modelo ao vivo
MIN_JOGOS = 3        # minimo de jogos previos pra arriscar uma previsao


# ---------- coleta dos registros (jogo + stats), com cache em disco ----------

def _cartoes(st_time: dict) -> float | None:
    am = st_time.get(STAT_CARTAO_AMARELO)
    ver = st_time.get(STAT_CARTAO_VERMELHO)
    if am is None and ver is None:
        return None
    return (am or 0) + (ver or 0)


def coletar_registros(comp_id: int, d1: str, d2: str) -> list[dict]:
    vistos = {}
    for ja, jb in _janelas(d1, d2):
        for g in listar_jogos(comp_id, ja, jb):
            if _finalizado(g):
                vistos[g["id"]] = g
    registros = []
    for g in sorted(vistos.values(), key=lambda x: x.get("startTime", "")):
        hc, ac = g["homeCompetitor"], g["awayCompetitor"]
        try:
            st = stats_partida(g["id"])
        except Exception:
            st = {}
        sh, sa = st.get(hc["id"], {}), st.get(ac["id"], {})
        registros.append({
            "data": g["startTime"][:10], "home": hc["name"], "away": ac["name"],
            "gh": float(hc["score"]), "ga": float(ac["score"]),
            "xg_h": sh.get(STAT_XG), "xg_a": sa.get(STAT_XG),
            "cf_h": sh.get(STAT_ESCANTEIOS), "cf_a": sa.get(STAT_ESCANTEIOS),
            "ca_h": _cartoes(sh), "ca_a": _cartoes(sa),
        })
    return registros


# ---------- forma de um time ANTES de uma data (sem look-ahead) ----------

def construir_historico(registros: list[dict]) -> dict[str, list[tuple]]:
    hist = defaultdict(list)
    for r in registros:
        # (data, gf, ga, xg, xga, esc_feitos, esc_sofridos, cartoes)
        hist[r["home"]].append((r["data"], r["gh"], r["ga"], r["xg_h"], r["xg_a"],
                                r["cf_h"], r["cf_a"], r["ca_h"]))
        hist[r["away"]].append((r["data"], r["ga"], r["gh"], r["xg_a"], r["xg_h"],
                                r["cf_a"], r["cf_h"], r["ca_a"]))
    return hist


def stats_antes(hist, time_nome, data, lookback_dias=LOOKBACK_DIAS):
    corte = (datetime.strptime(data, "%Y-%m-%d") - timedelta(days=lookback_dias)).strftime("%Y-%m-%d")
    prev = [e for e in hist.get(time_nome, []) if corte <= e[0] < data]
    if len(prev) < MIN_JOGOS:
        return None

    def med(idx):
        vals = [e[idx] for e in prev if e[idx] is not None]
        return sum(vals) / len(vals) if vals else None

    return EstatisticasTime(
        nome=time_nome, jogos=len(prev),
        gols_feitos_por_jogo=med(1), gols_sofridos_por_jogo=med(2),
        xg_por_jogo=med(3), xga_por_jogo=med(4),
        escanteios_feitos_por_jogo=med(5), escanteios_sofridos_por_jogo=med(6),
        cartoes_por_jogo=med(7),
    )


# ---------- coletores de metrica ----------

def _clip(p):
    return min(1 - 1e-6, max(1e-6, p))


class Binario:
    def __init__(self, nome):
        self.nome = nome
        self.ps = []
        self.ys = []

    def add(self, p, y):
        self.ps.append(p)
        self.ys.append(1 if y else 0)

    def resumo(self):
        n = len(self.ys)
        if n == 0:
            return None
        base = sum(self.ys) / n
        brier = sum((p - y) ** 2 for p, y in zip(self.ps, self.ys)) / n
        logloss = -sum(y * log(_clip(p)) + (1 - y) * log(1 - _clip(p))
                       for p, y in zip(self.ps, self.ys)) / n
        brier_base = sum((base - y) ** 2 for y in self.ys) / n
        ll_base = -sum(y * log(_clip(base)) + (1 - y) * log(1 - _clip(base))
                       for y in self.ys) / n
        return dict(n=n, base=base, brier=brier, logloss=logloss,
                    brier_base=brier_base, ll_base=ll_base)

    def calibracao(self, faixas=5):
        bins = [[] for _ in range(faixas)]
        for p, y in zip(self.ps, self.ys):
            idx = min(faixas - 1, int(p * faixas))
            bins[idx].append((p, y))
        linhas = []
        for i, b in enumerate(bins):
            if not b:
                continue
            mp = sum(p for p, _ in b) / len(b)
            my = sum(y for _, y in b) / len(b)
            linhas.append((f"{i/faixas:.0%}-{(i+1)/faixas:.0%}", len(b), mp, my))
        return linhas


class Tripla:  # 1X2
    def __init__(self):
        self.ps = []
        self.idx = []

    def add(self, p3, i):
        self.ps.append(p3)
        self.idx.append(i)

    def resumo(self):
        n = len(self.idx)
        if n == 0:
            return None
        brier = sum(sum((p3[c] - (1 if c == i else 0)) ** 2 for c in range(3))
                    for p3, i in zip(self.ps, self.idx)) / n
        logloss = -sum(log(_clip(p3[i])) for p3, i in zip(self.ps, self.idx)) / n
        freq = [self.idx.count(c) / n for c in range(3)]
        brier_base = sum(sum((freq[c] - (1 if c == i else 0)) ** 2 for c in range(3))
                         for i in self.idx) / n
        ll_base = -sum(log(_clip(freq[i])) for i in self.idx) / n
        return dict(n=n, brier=brier, logloss=logloss,
                    brier_base=brier_base, ll_base=ll_base, freq=freq)


def main(dias=90):
    fim = datetime.now()
    d2 = fim.strftime("%d/%m/%Y")
    d1 = (fim - timedelta(days=dias)).strftime("%d/%m/%Y")
    print(f"\n=== BACKTEST ({d1} a {d2}, janela {LOOKBACK_DIAS}d) ===\n")

    x12 = Tripla()
    o05, o15, o25 = Binario("+0.5 gols"), Binario("+1.5 gols"), Binario("+2.5 gols")
    btts = Binario("Ambas marcam")
    esc = Binario("+9.5 escanteios")
    cart = Binario("+4.5 cartões")
    total_prev = pulados = 0

    for liga_key, comp in COMPETICOES_365.items():
        print(f"[{LIGAS[liga_key]['nome']}] coletando...", flush=True)
        registros = coletar_registros(comp, d1, d2)
        hist = construir_historico(registros)
        liga = parametros_da_liga(liga_key)
        prev_liga = 0
        for r in registros:
            tm = stats_antes(hist, r["home"], r["data"])
            tv = stats_antes(hist, r["away"], r["data"])
            if not tm or not tv:
                pulados += 1
                continue
            lam_m, lam_v = gols_esperados(tm, tv, liga)
            m = calcular_mercados(lam_m, lam_v,
                                  lam_escanteios=escanteios_esperados(tm, tv, liga),
                                  lam_cartoes=cartoes_esperados(tm, tv, liga))
            gh, ga = r["gh"], r["ga"]
            tot = gh + ga
            res = 0 if gh > ga else (1 if gh == ga else 2)
            x12.add((m.vitoria_mandante, m.empate, m.vitoria_visitante), res)
            o05.add(m.over_05, tot >= 1)
            o15.add(m.over_15, tot >= 2)
            o25.add(m.over_25, tot >= 3)
            btts.add(m.ambas_marcam, gh >= 1 and ga >= 1)
            if m.escanteios and r["cf_h"] is not None and r["cf_a"] is not None:
                esc.add(m.escanteios["over_9_5"], (r["cf_h"] + r["cf_a"]) > 9.5)
            if m.cartoes and r["ca_h"] is not None and r["ca_a"] is not None:
                cart.add(m.cartoes["over_4_5"], (r["ca_h"] + r["ca_a"]) > 4.5)
            prev_liga += 1
        total_prev += prev_liga
        print(f"   {len(registros)} jogos finalizados, {prev_liga} previsoes validas")

    print(f"\nTotal: {total_prev} previsoes ({pulados} pulados por falta de historico)\n")
    if total_prev == 0:
        print("Sem dados suficientes para avaliar.")
        return

    def veredito(metrica, base):
        return "(melhor que baseline)" if metrica < base else "(NAO ganha do baseline)"

    # 1X2
    r = x12.resumo()
    print("== RESULTADO (1X2) ==")
    print(f"  n={r['n']}  Brier={r['brier']:.3f} (baseline {r['brier_base']:.3f})  "
          f"LogLoss={r['logloss']:.3f} (baseline {r['ll_base']:.3f})")
    print(f"  -> {veredito(r['logloss'], r['ll_base'])}")

    # binarios
    for col in (o05, o15, o25, btts, esc, cart):
        s = col.resumo()
        if not s:
            continue
        print(f"\n== {col.nome.upper()} ==")
        print(f"  n={s['n']}  taxa real={s['base']:.0%}  "
              f"Brier={s['brier']:.3f} (base {s['brier_base']:.3f})  "
              f"LogLoss={s['logloss']:.3f} (base {s['ll_base']:.3f})  {veredito(s['logloss'], s['ll_base'])}")
        print(f"  {'faixa':>10} {'jogos':>6} {'previsto':>9} {'real':>7}  desvio")
        for faixa, nb, mp, my in col.calibracao():
            nota = "subestima" if my > mp + 0.05 else ("superestima" if my < mp - 0.05 else "ok")
            print(f"  {faixa:>10} {nb:>6} {mp:>8.0%} {my:>7.0%}  {nota}")

    print("\nLeitura: Brier/LogLoss menor que o baseline = o modelo agrega informacao.")
    print("Na calibracao, 'previsto' deve bater com 'real' em cada faixa.\n")


if __name__ == "__main__":
    dias = 90
    if "--dias" in sys.argv:
        dias = int(sys.argv[sys.argv.index("--dias") + 1])
    main(dias=dias)
