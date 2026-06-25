"""
Motor estatistico Poisson para futebol.

A ideia central: o numero de gols de um time numa partida segue aproximadamente
uma distribuicao de Poisson. Se eu souber quantos gols cada time TENDE a fazer
nessa partida (o "gol esperado", lambda), eu consigo calcular a probabilidade de
qualquer placar e, somando os placares certos, a probabilidade de qualquer mercado:

  - Resultado (1X2): vitoria mandante / empate / vitoria visitante
  - Over/Under (2.5, 1.5, etc.)
  - Ambas marcam (BTTS)
  - Escanteios (mesma matematica, com lambda de escanteios)

Nada aqui usa odds. Tudo sai de estatistica (gols/escanteios feitos e sofridos).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, factorial


def poisson_pmf(k: int, lam: float) -> float:
    """Probabilidade de exatamente k eventos quando a media esperada e lam."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * exp(-lam) / factorial(k)


@dataclass
class ResultadoMercados:
    """Todas as probabilidades de uma partida, em fracao (0-1)."""

    # 1X2
    vitoria_mandante: float
    empate: float
    vitoria_visitante: float

    # Over/Under gols
    over_05: float
    over_15: float
    over_25: float
    over_35: float

    # Ambas marcam
    ambas_marcam: float

    # Gols esperados usados no calculo (transparencia)
    gols_esperados_mandante: float
    gols_esperados_visitante: float

    # Placar mais provavel
    placar_provavel: tuple[int, int]
    prob_placar_provavel: float

    # Escanteios (preenchido so se houver dados) - over X.5
    escanteios: dict[str, float] = field(default_factory=dict)
    escanteios_esperados: float = 0.0

    def pct(self, valor: float) -> int:
        """Converte fracao em % inteira para exibicao."""
        return round(valor * 100)


def matriz_placares(lam_mandante: float, lam_visitante: float, max_gols: int = 10):
    """Matriz de probabilidade de cada placar (i gols mandante, j gols visitante)."""
    p_mandante = [poisson_pmf(i, lam_mandante) for i in range(max_gols + 1)]
    p_visitante = [poisson_pmf(j, lam_visitante) for j in range(max_gols + 1)]
    matriz = [[p_mandante[i] * p_visitante[j] for j in range(max_gols + 1)]
              for i in range(max_gols + 1)]
    return matriz


def calcular_mercados(lam_mandante: float, lam_visitante: float,
                      lam_escanteios: float | None = None,
                      max_gols: int = 10) -> ResultadoMercados:
    """
    Recebe os gols esperados de cada time (lambda) e devolve todas as
    probabilidades dos mercados.
    """
    matriz = matriz_placares(lam_mandante, lam_visitante, max_gols)

    vit_mandante = empate = vit_visitante = 0.0
    over_05 = over_15 = over_25 = over_35 = 0.0
    ambas = 0.0
    melhor_placar = (0, 0)
    melhor_prob = 0.0

    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            p = matriz[i][j]

            # 1X2
            if i > j:
                vit_mandante += p
            elif i == j:
                empate += p
            else:
                vit_visitante += p

            # Over/Under (total de gols)
            total = i + j
            if total >= 1:
                over_05 += p
            if total >= 2:
                over_15 += p
            if total >= 3:
                over_25 += p
            if total >= 4:
                over_35 += p

            # Ambas marcam
            if i >= 1 and j >= 1:
                ambas += p

            # Placar mais provavel
            if p > melhor_prob:
                melhor_prob = p
                melhor_placar = (i, j)

    escanteios = {}
    esc_esperados = 0.0
    if lam_escanteios is not None and lam_escanteios > 0:
        esc_esperados = lam_escanteios
        for linha in (7.5, 8.5, 9.5, 10.5, 11.5):
            # P(total escanteios > linha)
            limite = int(linha)  # ex linha 9.5 -> over se >=10
            acumulado = sum(poisson_pmf(k, lam_escanteios) for k in range(0, limite + 1))
            escanteios[f"over_{str(linha).replace('.', '_')}"] = 1.0 - acumulado

    return ResultadoMercados(
        vitoria_mandante=vit_mandante,
        empate=empate,
        vitoria_visitante=vit_visitante,
        over_05=over_05,
        over_15=over_15,
        over_25=over_25,
        over_35=over_35,
        ambas_marcam=ambas,
        gols_esperados_mandante=lam_mandante,
        gols_esperados_visitante=lam_visitante,
        placar_provavel=melhor_placar,
        prob_placar_provavel=melhor_prob,
        escanteios=escanteios,
        escanteios_esperados=esc_esperados,
    )


def handicap_asiatico(lam_mandante: float, lam_visitante: float,
                      linha: float, max_gols: int = 10) -> dict[str, float]:
    """
    Probabilidades de Handicap Asiatico para uma linha (ex: -0.5, -1.0, +1.5)
    aplicada ao MANDANTE. Devolve prob de cobrir (mandante), do visitante e push.

    Linha -1.0 no mandante: mandante precisa vencer por 2+ pra ganhar a aposta;
    por exatamente 1 e push (devolve); empate ou derrota perde.
    """
    matriz = matriz_placares(lam_mandante, lam_visitante, max_gols)
    p_mandante = p_visitante = p_push = 0.0

    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            p = matriz[i][j]
            margem = (i - j) + linha  # diferenca ajustada pela linha
            if margem > 0:
                p_mandante += p
            elif margem < 0:
                p_visitante += p
            else:
                p_push += p

    return {"mandante": p_mandante, "visitante": p_visitante, "push": p_push}
