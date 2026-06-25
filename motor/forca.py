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
    """Medias da liga inteira, base para normalizar a forca dos times."""
    media_gols_mandante: float = 1.45   # gols medios do mandante por jogo
    media_gols_visitante: float = 1.15  # gols medios do visitante por jogo
    media_escanteios_time: float = 5.0  # escanteios medios de um time por jogo


def gols_esperados(mandante: EstatisticasTime, visitante: EstatisticasTime,
                   liga: ParametrosLiga) -> tuple[float, float]:
    """Devolve (lambda_mandante, lambda_visitante)."""
    media_total = (liga.media_gols_mandante + liga.media_gols_visitante) / 2

    ataque_m = mandante.ataque_efetivo() / media_total
    defesa_m = mandante.defesa_efetiva() / media_total
    ataque_v = visitante.ataque_efetivo() / media_total
    defesa_v = visitante.defesa_efetiva() / media_total

    lam_m = liga.media_gols_mandante * ataque_m * defesa_v
    lam_v = liga.media_gols_visitante * ataque_v * defesa_m

    # trava de seguranca pra nao explodir com amostras pequenas
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

    # escanteios do mandante = media entre (o que ele obtem) e (o que o visitante cede)
    esc_m = (mandante.escanteios_feitos_por_jogo +
             (visitante.escanteios_sofridos_por_jogo or media)) / 2
    esc_v = (visitante.escanteios_feitos_por_jogo +
             (mandante.escanteios_sofridos_por_jogo or media)) / 2

    total = esc_m + esc_v
    return max(4.0, min(total, 16.0))
