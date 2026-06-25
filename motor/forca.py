"""
Calcula a FORCA de cada time a partir das estatisticas dos ultimos jogos e
converte num "gol esperado" (lambda) para uma partida especifica.

Metodo (padrao academico, usado por casas serias - mas aqui SEM odds):

  forca_ataque(time)  = (gols feitos por jogo do time) / (media de gols da liga)
  forca_defesa(time)  = (gols sofridos por jogo do time) / (media de gols da liga)

  gols_esperados_mandante = media_liga_mandante * ataque(mandante) * defesa(visitante)
  gols_esperados_visitante = media_liga_visitante * ataque(visitante) * defesa(mandante)

Quando temos xG (gols esperados do FBref), usamos uma media entre gols reais e xG,
porque o xG e mais estavel e preve melhor o futuro do que so o placar.

Mesma logica vale para escanteios.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EstatisticasTime:
    """Medias por jogo de um time (em geral dos ultimos N jogos)."""
    nome: str
    jogos: int
    gols_feitos_por_jogo: float
    gols_sofridos_por_jogo: float
    xg_por_jogo: float | None = None          # gols esperados (ataque)
    xga_por_jogo: float | None = None         # gols esperados sofridos (defesa)
    escanteios_feitos_por_jogo: float | None = None
    escanteios_sofridos_por_jogo: float | None = None
    cartoes_por_jogo: float | None = None   # cartoes (amarelo+vermelho) recebidos por jogo

    def ataque_efetivo(self) -> float:
        """Combina gols reais e xG (peso 60% xG por ser mais estavel)."""
        if self.xg_por_jogo is not None:
            return 0.4 * self.gols_feitos_por_jogo + 0.6 * self.xg_por_jogo
        return self.gols_feitos_por_jogo

    def defesa_efetiva(self) -> float:
        if self.xga_por_jogo is not None:
            return 0.4 * self.gols_sofridos_por_jogo + 0.6 * self.xga_por_jogo
        return self.gols_sofridos_por_jogo


@dataclass
class ParametrosLiga:
    """
    Medias da liga inteira, base para normalizar a forca dos times.

    campo_neutro=True (ex: Copa do Mundo): zera a vantagem de casa, porque o
    "mandante" do feed e arbitrario. Nesse caso media_gols_mandante e visitante
    sao igualadas, e nenhum time ganha vantagem por estar "em casa".

    peso_prior (k) controla o shrinkage: com poucos jogos a forca do time regride
    para a media da liga. k em "numero de jogos equivalentes" do prior.
    """
    media_gols_mandante: float = 1.45   # gols medios do mandante por jogo
    media_gols_visitante: float = 1.15  # gols medios do visitante por jogo
    media_escanteios_time: float = 5.0  # escanteios medios de um time por jogo
    media_cartoes_time: float = 2.0     # cartoes medios de um time por jogo
    peso_prior: float = 5.0             # k do shrinkage (jogos equivalentes)
    campo_neutro: bool = False

    def medias_gol(self) -> tuple[float, float]:
        """(media_mandante, media_visitante) ja tratando campo neutro."""
        if self.campo_neutro:
            m = (self.media_gols_mandante + self.media_gols_visitante) / 2
            return m, m
        return self.media_gols_mandante, self.media_gols_visitante


def _encolher(valor: float, n: int | None, prior: float, k: float) -> float:
    """
    Shrinkage bayesiano: combina a estatistica do time com o prior da liga,
    ponderado pelo numero de jogos. Com n pequeno, puxa para o prior.
        ajustado = (n*valor + k*prior) / (n + k)
    """
    n = max(0, n or 0)
    return (n * valor + k * prior) / (n + k)


def gols_esperados(mandante: EstatisticasTime, visitante: EstatisticasTime,
                   liga: ParametrosLiga) -> tuple[float, float]:
    """Devolve (lambda_mandante, lambda_visitante)."""
    media_mand, media_vis = liga.medias_gol()
    media_total = (media_mand + media_vis) / 2
    k = liga.peso_prior

    # shrinkage: ataque/defesa de cada time regridem para a media da liga
    atk_m = _encolher(mandante.ataque_efetivo(), mandante.jogos, media_total, k)
    def_m = _encolher(mandante.defesa_efetiva(), mandante.jogos, media_total, k)
    atk_v = _encolher(visitante.ataque_efetivo(), visitante.jogos, media_total, k)
    def_v = _encolher(visitante.defesa_efetiva(), visitante.jogos, media_total, k)

    ataque_m, defesa_m = atk_m / media_total, def_m / media_total
    ataque_v, defesa_v = atk_v / media_total, def_v / media_total

    lam_m = media_mand * ataque_m * defesa_v
    lam_v = media_vis * ataque_v * defesa_m

    # ultima rede de seguranca (nao deve mais ser atingida com shrinkage)
    lam_m = max(0.15, min(lam_m, 5.0))
    lam_v = max(0.15, min(lam_v, 5.0))
    return lam_m, lam_v


def escanteios_esperados(mandante: EstatisticasTime, visitante: EstatisticasTime,
                         liga: ParametrosLiga) -> float | None:
    """
    Total de escanteios esperados na partida. Usa o cruzamento entre os
    escanteios que um time costuma OBTER e os que o adversario costuma CEDER.
    """
    if (mandante.escanteios_feitos_por_jogo is None or
            visitante.escanteios_feitos_por_jogo is None):
        return None

    media = liga.media_escanteios_time
    k = liga.peso_prior

    # estatisticas encolhidas para a media da liga (amostra pequena -> media)
    mf = _encolher(mandante.escanteios_feitos_por_jogo, mandante.jogos, media, k)
    ms = _encolher(mandante.escanteios_sofridos_por_jogo or media, mandante.jogos, media, k)
    vf = _encolher(visitante.escanteios_feitos_por_jogo, visitante.jogos, media, k)
    vs = _encolher(visitante.escanteios_sofridos_por_jogo or media, visitante.jogos, media, k)

    # escanteios do mandante = media entre (o que ele obtem) e (o que o visitante cede)
    esc_m = (mf + vs) / 2
    esc_v = (vf + ms) / 2

    total = esc_m + esc_v
    return max(4.0, min(total, 16.0))


def cartoes_esperados(mandante: EstatisticasTime, visitante: EstatisticasTime,
                      liga: ParametrosLiga) -> float | None:
    """
    Total de cartoes esperados na partida = cartoes que cada time costuma
    receber por jogo, somados (com shrinkage para a media da liga).
    """
    if mandante.cartoes_por_jogo is None or visitante.cartoes_por_jogo is None:
        return None
    media = liga.media_cartoes_time
    k = liga.peso_prior
    cm = _encolher(mandante.cartoes_por_jogo, mandante.jogos, media, k)
    cv = _encolher(visitante.cartoes_por_jogo, visitante.jogos, media, k)
    total = cm + cv
    return max(1.0, min(total, 12.0))
