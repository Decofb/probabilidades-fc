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

    # Cartoes (preenchido so se houver dados) - over X.5
    cartoes: dict[str, float] = field(default_factory=dict)
    cartoes_esperados: float = 0.0

    def pct(self, valor: float) -> int:
        """Converte fracao em % inteira para exibicao."""
        return round(valor * 100)


# Parametro de correlacao de Dixon-Coles. Negativo aumenta placares 0-0/1-1
# (empates) e reduz 1-0/0-1, corrigindo o vies do Poisson independente puro.
RHO_DIXON_COLES = -0.06


def _tau_dixon_coles(i: int, j: int, lam_m: float, lam_v: float, rho: float) -> float:
    """Fator de correcao aplicado aos quatro placares baixos."""
    if i == 0 and j == 0:
        return 1.0 - lam_m * lam_v * rho
    if i == 0 and j == 1:
        return 1.0 + lam_m * rho
    if i == 1 and j == 0:
        return 1.0 + lam_v * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def matriz_placares(lam_mandante: float, lam_visitante: float, max_gols: int = 10,
                    rho: float = RHO_DIXON_COLES):
    """
    Matriz de probabilidade de cada placar (i gols mandante, j gols visitante),
    com correcao de Dixon-Coles nos placares baixos e renormalizada para somar 1.
    """
    p_mandante = [poisson_pmf(i, lam_mandante) for i in range(max_gols + 1)]
    p_visitante = [poisson_pmf(j, lam_visitante) for j in range(max_gols + 1)]
    matriz = [[p_mandante[i] * p_visitante[j]
               * _tau_dixon_coles(i, j, lam_mandante, lam_visitante, rho)
               for j in range(max_gols + 1)]
              for i in range(max_gols + 1)]

    total = sum(sum(linha) for linha in matriz)
    if total > 0:
        matriz = [[c / total for c in linha] for linha in matriz]
    return matriz


def nbinom_pmf(k: int, media: float, r: float) -> float:
    """
    Binomial Negativa parametrizada por media (mu) e dispersao r.
    Variancia = mu + mu^2/r  ->  r grande aproxima Poisson; r pequeno = mais cauda.
    Usada para escanteios/cartoes, que sao sobredispersos (Poisson erra as caudas).
    """
    from math import lgamma, log, exp
    if media <= 0 or r <= 0:
        return 1.0 if k == 0 else 0.0
    p = r / (r + media)
    return exp(lgamma(k + r) - lgamma(r) - lgamma(k + 1) + r * log(p) + k * log(1 - p))


def _over_lines(lam: float, linhas, dispersao: float | None = None) -> dict[str, float]:
    """
    P(total > linha) para cada linha X.5. Poisson por padrao; Binomial Negativa
    quando 'dispersao' (r) e informada (melhor para escanteios/cartoes).
    """
    out = {}
    for linha in linhas:
        limite = int(linha)  # linha 9.5 -> over se total >= 10
        if dispersao is not None and dispersao > 0:
            acumulado = sum(nbinom_pmf(k, lam, dispersao) for k in range(0, limite + 1))
        else:
            acumulado = sum(poisson_pmf(k, lam) for k in range(0, limite + 1))
        out[f"over_{str(linha).replace('.', '_')}"] = 1.0 - acumulado
    return out


def calcular_mercados(lam_mandante: float, lam_visitante: float,
                      lam_escanteios: float | None = None,
                      lam_cartoes: float | None = None,
                      rho: float = RHO_DIXON_COLES,
                      disp_escanteios: float | None = None,
                      disp_cartoes: float | None = None,
                      max_gols: int = 10) -> ResultadoMercados:
    """
    Recebe os gols esperados de cada time (lambda) e devolve todas as
    probabilidades dos mercados. rho = correlacao Dixon-Coles; disp_* = dispersao
    da Binomial Negativa para escanteios/cartoes (None = Poisson).
    """
    matriz = matriz_placares(lam_mandante, lam_visitante, max_gols, rho)

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
        escanteios = _over_lines(lam_escanteios, (7.5, 8.5, 9.5, 10.5, 11.5), disp_escanteios)

    cartoes = {}
    cart_esperados = 0.0
    if lam_cartoes is not None and lam_cartoes > 0:
        cart_esperados = lam_cartoes
        cartoes = _over_lines(lam_cartoes, (2.5, 3.5, 4.5, 5.5, 6.5), disp_cartoes)

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
        cartoes=cartoes,
        cartoes_esperados=cart_esperados,
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
