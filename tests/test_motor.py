"""
Rede de seguranca do motor estatistico. Trava os invariantes que NUNCA podem
quebrar: probabilidades somam ~1, mercados sao monotonicos, handicap fecha 100%.
Roda com:  python -m pytest -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.poisson import (poisson_pmf, calcular_mercados, handicap_asiatico,
                           matriz_placares)
from motor.forca import (EstatisticasTime, ParametrosLiga, gols_esperados)

TOL = 2e-3  # tolerancia pela truncagem em max_gols


# ---------- poisson_pmf ----------

def test_pmf_lambda_zero():
    assert poisson_pmf(0, 0) == 1.0
    assert poisson_pmf(1, 0) == 0.0


def test_pmf_soma_um():
    s = sum(poisson_pmf(k, 1.7) for k in range(0, 40))
    assert abs(s - 1.0) < 1e-9


# ---------- 1X2 ----------

def test_1x2_soma_um():
    m = calcular_mercados(1.5, 1.2)
    soma = m.vitoria_mandante + m.empate + m.vitoria_visitante
    assert abs(soma - 1.0) < TOL


def test_1x2_favorito_tem_mais_chance():
    m = calcular_mercados(2.4, 0.6)  # mandante MUITO mais forte
    assert m.vitoria_mandante > m.vitoria_visitante
    assert m.vitoria_mandante > m.empate


# ---------- Over/Under ----------

def test_over_monotonico():
    m = calcular_mercados(1.6, 1.3)
    assert m.over_05 > m.over_15 > m.over_25 > m.over_35
    for v in (m.over_05, m.over_15, m.over_25, m.over_35):
        assert 0.0 <= v <= 1.0


def test_over05_quase_certo_em_jogo_aberto():
    m = calcular_mercados(2.0, 1.8)
    assert m.over_05 > 0.90


# ---------- BTTS ----------

def test_btts_intervalo():
    m = calcular_mercados(1.4, 1.1)
    assert 0.0 <= m.ambas_marcam <= 1.0


def test_btts_baixo_quando_um_time_quase_nao_marca():
    m = calcular_mercados(2.0, 0.2)
    assert m.ambas_marcam < 0.30


# ---------- Handicap asiatico ----------

def test_handicap_fecha_cem_por_cento():
    for linha in (-1.0, -0.5, 0.0, 0.5, 1.0):
        h = handicap_asiatico(1.6, 1.2, linha)
        soma = h["mandante"] + h["visitante"] + h["push"]
        assert abs(soma - 1.0) < TOL, f"linha {linha} somou {soma}"


def test_handicap_linha_inteira_tem_push():
    h = handicap_asiatico(1.5, 1.5, -1.0)
    assert h["push"] > 0.0  # margem exata de 1 gol e devolucao


def test_handicap_meia_linha_sem_push():
    h = handicap_asiatico(1.5, 1.5, -0.5)
    assert h["push"] < TOL


# ---------- Escanteios / Cartoes ----------

def test_escanteios_monotonico():
    m = calcular_mercados(1.5, 1.2, lam_escanteios=9.5)
    vals = [m.escanteios[k] for k in ("over_7_5", "over_8_5", "over_9_5", "over_10_5", "over_11_5")]
    assert vals == sorted(vals, reverse=True)


def test_cartoes_monotonico():
    m = calcular_mercados(1.5, 1.2, lam_cartoes=4.5)
    vals = [m.cartoes[k] for k in ("over_2_5", "over_3_5", "over_4_5", "over_5_5", "over_6_5")]
    assert vals == sorted(vals, reverse=True)


def test_sem_dados_extras_nao_gera_mercado():
    m = calcular_mercados(1.5, 1.2)
    assert m.escanteios == {} and m.cartoes == {}


# ---------- Matriz ----------

def test_matriz_soma_aproxima_um():
    mat = matriz_placares(1.5, 1.2)
    total = sum(sum(linha) for linha in mat)
    assert abs(total - 1.0) < TOL


# ---------- Binomial Negativa (escanteios/cartoes) ----------

def test_nbinom_soma_um():
    from motor.poisson import nbinom_pmf
    s = sum(nbinom_pmf(k, 9.9, 31.7) for k in range(0, 80))
    assert abs(s - 1.0) < 1e-6


def test_escanteios_nb_monotonico():
    m = calcular_mercados(1.5, 1.2, lam_escanteios=9.5, disp_escanteios=20)
    vals = [m.escanteios[k] for k in ("over_7_5", "over_8_5", "over_9_5", "over_10_5", "over_11_5")]
    assert vals == sorted(vals, reverse=True)


def test_nb_mais_cauda_que_poisson():
    # com sobredispersao, P(over numa linha alta) >= Poisson
    pois = calcular_mercados(1.5, 1.2, lam_cartoes=4.5)
    nb = calcular_mercados(1.5, 1.2, lam_cartoes=4.5, disp_cartoes=8)
    assert nb.cartoes["over_6_5"] >= pois.cartoes["over_6_5"] - 1e-9
