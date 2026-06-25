"""
Testes das CORRECOES do modelo: campo neutro, vantagem de casa, shrinkage
e Dixon-Coles. Travam os achados P0/P1/P2 da auditoria.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.forca import EstatisticasTime, ParametrosLiga, gols_esperados
from motor.poisson import calcular_mercados, matriz_placares
from config import parametros_da_liga


def _time(nome, jogos, gf, gs):
    return EstatisticasTime(nome, jogos=jogos, gols_feitos_por_jogo=gf,
                            gols_sofridos_por_jogo=gs)


# ---------- P0: campo neutro nao da vantagem de casa ----------

def test_copa_campo_neutro_e_simetrico():
    liga = parametros_da_liga("copa_mundo")
    assert liga.campo_neutro is True
    a, b = _time("A", 5, 1.5, 1.0), _time("B", 5, 1.5, 1.0)  # times identicos
    lam_m, lam_v = gols_esperados(a, b, liga)
    assert abs(lam_m - lam_v) < 1e-9  # nenhum lado ganha por ser "mandante"
    m = calcular_mercados(lam_m, lam_v)
    assert abs(m.vitoria_mandante - m.vitoria_visitante) < 1e-6


def test_brasileirao_tem_vantagem_de_casa():
    liga = parametros_da_liga("brasileirao_a")
    assert liga.campo_neutro is False
    a, b = _time("A", 10, 1.3, 1.1), _time("B", 10, 1.3, 1.1)  # identicos
    lam_m, lam_v = gols_esperados(a, b, liga)
    assert lam_m > lam_v  # mandante leva vantagem real de casa
    m = calcular_mercados(lam_m, lam_v)
    assert m.vitoria_mandante > m.vitoria_visitante


# ---------- P1: shrinkage com amostra pequena ----------

def test_shrinkage_suaviza_amostra_pequena():
    liga = ParametrosLiga(campo_neutro=True)
    adv = _time("Adv", 10, 1.2, 1.2)
    forte_2jogos = _time("F", 2, 4.0, 0.2)    # extremo, poucos jogos
    forte_30jogos = _time("F", 30, 4.0, 0.2)  # mesmo extremo, muitos jogos
    lam_2, _ = gols_esperados(forte_2jogos, adv, liga)
    lam_30, _ = gols_esperados(forte_30jogos, adv, liga)
    # com poucos jogos, a forca regride para a media -> lambda menos extremo
    assert lam_2 < lam_30


def test_shrinkage_evita_probabilidade_absurda():
    liga = parametros_da_liga("copa_mundo")
    forte = _time("Forte", 2, 4.0, 0.0)   # 2 jogos, 0 sofridos
    fraco = _time("Fraco", 2, 0.0, 4.0)
    lam_m, lam_v = gols_esperados(forte, fraco, liga)
    m = calcular_mercados(lam_m, lam_v)
    # nao deve cuspir 99%+/0% so por causa de 2 jogos extremos
    assert m.vitoria_mandante < 0.95
    assert m.vitoria_visitante > 0.01


# ---------- P2: Dixon-Coles aumenta empate ----------

def test_dixon_coles_aumenta_empate():
    def prob_empate(mat):
        return sum(mat[i][i] for i in range(len(mat)))
    com_dc = matriz_placares(1.4, 1.2, rho=-0.06)
    sem_dc = matriz_placares(1.4, 1.2, rho=0.0)
    assert prob_empate(com_dc) > prob_empate(sem_dc)


def test_matriz_sempre_soma_um_com_dixon_coles():
    mat = matriz_placares(2.1, 0.9, rho=-0.06)
    total = sum(sum(linha) for linha in mat)
    assert abs(total - 1.0) < 1e-9
