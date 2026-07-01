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
    # Força relativa via ranking FIFA/ELO (1.0 = time médio da competição).
    forca_elo: float = 1.0
    # Splits casa / fora — preenchidos pelo scores365 com time decay (melhoria 3)
    gols_feitos_casa_por_jogo: float | None = None
    gols_sofridos_casa_por_jogo: float | None = None
    jogos_casa: int = 0
    gols_feitos_fora_por_jogo: float | None = None
    gols_sofridos_fora_por_jogo: float | None = None
    jogos_fora: int = 0

    def ataque_efetivo(self, peso_xg: float = 0.6) -> float:
        """Combina gols reais e xG (peso_xg = quanto o xG pesa, por ser mais estavel)."""
        if self.xg_por_jogo is not None:
            return (1 - peso_xg) * self.gols_feitos_por_jogo + peso_xg * self.xg_por_jogo
        return self.gols_feitos_por_jogo

    def defesa_efetiva(self, peso_xg: float = 0.6) -> float:
        if self.xga_por_jogo is not None:
            return (1 - peso_xg) * self.gols_sofridos_por_jogo + peso_xg * self.xga_por_jogo
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
    peso_xg: float = 0.6                # quanto o xG pesa vs gols reais (0..1)
    campo_neutro: bool = False
    # dispersao da Binomial Negativa (estimada empiricamente no otimizar.py).
    # Sobredispersao leve -> r alto, perto do Poisson. r mais baixo = mais cauda.
    disp_escanteios: float = 32.0
    disp_cartoes: float = 15.0

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


_MIN_JOGOS_CASA_FORA = 4  # mínimo para usar split casa/fora


def _ataque_fora(t: "EstatisticasTime", w: float) -> float:
    """Ataque do time jogando FORA de casa (visitante)."""
    if t.gols_feitos_fora_por_jogo is not None and t.jogos_fora >= _MIN_JOGOS_CASA_FORA:
        if t.xg_por_jogo is not None:
            # Aproximação: escala o xG pela proporção casa/fora em gols reais
            ratio = (t.gols_feitos_fora_por_jogo / max(t.gols_feitos_por_jogo, 0.1))
            xg_fora = t.xg_por_jogo * ratio
            return (1 - w) * t.gols_feitos_fora_por_jogo + w * xg_fora
        return t.gols_feitos_fora_por_jogo
    return t.ataque_efetivo(w)


def _defesa_fora(t: "EstatisticasTime", w: float) -> float:
    """Defesa do time jogando FORA (gols sofridos como visitante)."""
    if t.gols_sofridos_fora_por_jogo is not None and t.jogos_fora >= _MIN_JOGOS_CASA_FORA:
        if t.xga_por_jogo is not None:
            ratio = (t.gols_sofridos_fora_por_jogo / max(t.gols_sofridos_por_jogo, 0.1))
            xga_fora = t.xga_por_jogo * ratio
            return (1 - w) * t.gols_sofridos_fora_por_jogo + w * xga_fora
        return t.gols_sofridos_fora_por_jogo
    return t.defesa_efetiva(w)


def _ataque_casa(t: "EstatisticasTime", w: float) -> float:
    """Ataque do time jogando EM CASA."""
    if t.gols_feitos_casa_por_jogo is not None and t.jogos_casa >= _MIN_JOGOS_CASA_FORA:
        if t.xg_por_jogo is not None:
            ratio = (t.gols_feitos_casa_por_jogo / max(t.gols_feitos_por_jogo, 0.1))
            xg_casa = t.xg_por_jogo * ratio
            return (1 - w) * t.gols_feitos_casa_por_jogo + w * xg_casa
        return t.gols_feitos_casa_por_jogo
    return t.ataque_efetivo(w)


def _defesa_casa(t: "EstatisticasTime", w: float) -> float:
    """Defesa do time jogando EM CASA (gols sofridos como mandante)."""
    if t.gols_sofridos_casa_por_jogo is not None and t.jogos_casa >= _MIN_JOGOS_CASA_FORA:
        if t.xga_por_jogo is not None:
            ratio = (t.gols_sofridos_casa_por_jogo / max(t.gols_sofridos_por_jogo, 0.1))
            xga_casa = t.xga_por_jogo * ratio
            return (1 - w) * t.gols_sofridos_casa_por_jogo + w * xga_casa
        return t.gols_sofridos_casa_por_jogo
    return t.defesa_efetiva(w)


def gols_esperados(mandante: EstatisticasTime, visitante: EstatisticasTime,
                   liga: ParametrosLiga) -> tuple[float, float]:
    """Devolve (lambda_mandante, lambda_visitante)."""
    media_mand, media_vis = liga.medias_gol()
    media_total = (media_mand + media_vis) / 2
    k = liga.peso_prior
    w = liga.peso_xg
    elo_m, elo_v = mandante.forca_elo, visitante.forca_elo

    if liga.campo_neutro:
        # Copa: sem distinção casa/fora; usa estatísticas globais
        raw_atk_m = mandante.ataque_efetivo(w)
        raw_def_m = mandante.defesa_efetiva(w)
        raw_atk_v = visitante.ataque_efetivo(w)
        raw_def_v = visitante.defesa_efetiva(w)
        n_m, n_v = mandante.jogos, visitante.jogos
    else:
        # Brasileirão: usa split casa (mandante) / fora (visitante) — melhoria 3
        raw_atk_m = _ataque_casa(mandante, w)
        raw_def_m = _defesa_casa(mandante, w)
        raw_atk_v = _ataque_fora(visitante, w)
        raw_def_v = _defesa_fora(visitante, w)
        n_m = max(mandante.jogos_casa, 1) if mandante.jogos_casa >= _MIN_JOGOS_CASA_FORA else mandante.jogos
        n_v = max(visitante.jogos_fora, 1) if visitante.jogos_fora >= _MIN_JOGOS_CASA_FORA else visitante.jogos

    # shrinkage bayesiano com prior ajustado por ELO (atacar mais / sofrer menos)
    atk_m = _encolher(raw_atk_m, n_m, media_total * elo_m, k)
    def_m = _encolher(raw_def_m, n_m, media_total / elo_m, k)
    atk_v = _encolher(raw_atk_v, n_v, media_total * elo_v, k)
    def_v = _encolher(raw_def_v, n_v, media_total / elo_v, k)

    ataque_m, defesa_m = atk_m / media_total, def_m / media_total
    ataque_v, defesa_v = atk_v / media_total, def_v / media_total

    lam_m = media_mand * ataque_m * defesa_v
    lam_v = media_vis * ataque_v * defesa_m

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
