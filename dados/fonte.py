"""
Camada de dados: de onde vem a estatistica de cada time.

Estrategia (robusta de proposito):
  1. Tenta puxar do FBref via soccerdata (gols, xG, etc.).
  2. Se conseguir, salva num CSV (vira cache + base editavel).
  3. Se o FBref bloquear/demorar, usa o CSV que ja existe.

Assim o site NUNCA fica sem dados. O CSV tambem pode ser editado a mao
(no Excel) caso voce queira ajustar ou inserir um time manualmente.

Colunas do CSV de times:
  time, jogos, gols_feitos, gols_sofridos, xg, xga, esc_feitos, esc_sofridos
(todas as medias sao POR JOGO)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PASTA_DADOS, LIGAS, JANELA_JOGOS  # noqa: E402
from motor.forca import EstatisticasTime  # noqa: E402


def _caminho_csv(liga_key: str) -> Path:
    return PASTA_DADOS / f"{liga_key}_times.csv"


def salvar_times_csv(liga_key: str, times: dict[str, EstatisticasTime]) -> Path:
    caminho = _caminho_csv(liga_key)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "jogos", "gols_feitos", "gols_sofridos",
                    "xg", "xga", "esc_feitos", "esc_sofridos", "cartoes"])
        for t in times.values():
            w.writerow([
                t.nome, t.jogos,
                round(t.gols_feitos_por_jogo, 3), round(t.gols_sofridos_por_jogo, 3),
                "" if t.xg_por_jogo is None else round(t.xg_por_jogo, 3),
                "" if t.xga_por_jogo is None else round(t.xga_por_jogo, 3),
                "" if t.escanteios_feitos_por_jogo is None else round(t.escanteios_feitos_por_jogo, 3),
                "" if t.escanteios_sofridos_por_jogo is None else round(t.escanteios_sofridos_por_jogo, 3),
                "" if t.cartoes_por_jogo is None else round(t.cartoes_por_jogo, 3),
            ])
    return caminho


def carregar_times_csv(liga_key: str) -> dict[str, EstatisticasTime]:
    caminho = _caminho_csv(liga_key)
    if not caminho.exists():
        return {}
    times: dict[str, EstatisticasTime] = {}
    with caminho.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            def num(campo):
                v = row.get(campo, "")
                return float(v) if v not in ("", None) else None
            times[row["time"]] = EstatisticasTime(
                nome=row["time"],
                jogos=int(row["jogos"] or 0),
                gols_feitos_por_jogo=float(row["gols_feitos"]),
                gols_sofridos_por_jogo=float(row["gols_sofridos"]),
                xg_por_jogo=num("xg"),
                xga_por_jogo=num("xga"),
                escanteios_feitos_por_jogo=num("esc_feitos"),
                escanteios_sofridos_por_jogo=num("esc_sofridos"),
                cartoes_por_jogo=num("cartoes"),
            )
    return times


def buscar_fbref(liga_key: str) -> dict[str, EstatisticasTime]:
    """
    Tenta puxar estatisticas de temporada do FBref. Pode falhar/demorar
    (proteccao do site) - quem chama deve tratar a excecao.
    """
    import soccerdata as sd

    cfg = LIGAS[liga_key]
    fb = sd.FBref(leagues=cfg["fbref"], seasons=cfg["temporada"])

    padrao = fb.read_team_season_stats(stat_type="standard")
    padrao = padrao.reset_index()

    # nomes de coluna do FBref vem em MultiIndex; achatamos
    padrao.columns = ["_".join([str(c) for c in col if str(c) != ""]).strip("_")
                      if isinstance(col, tuple) else str(col)
                      for col in padrao.columns]

    def achar(df, *chaves):
        for c in df.columns:
            low = c.lower()
            if all(k in low for k in chaves):
                return c
        return None

    col_time = achar(padrao, "team") or "team"
    col_jogos = achar(padrao, "playing", "mp") or achar(padrao, "_mp") or achar(padrao, "mp")
    col_gf = achar(padrao, "performance", "gls") or achar(padrao, "_gls")
    col_xg = achar(padrao, "expected", "xg") or achar(padrao, "_xg")

    times: dict[str, EstatisticasTime] = {}
    for _, r in padrao.iterrows():
        try:
            jogos = float(r[col_jogos]) or 1
            gf = float(r[col_gf]) / jogos if col_gf else 1.2
            xg = (float(r[col_xg]) / jogos) if col_xg else None
        except (TypeError, ValueError):
            continue
        nome = str(r[col_time])
        times[nome] = EstatisticasTime(
            nome=nome, jogos=int(jogos),
            gols_feitos_por_jogo=gf, gols_sofridos_por_jogo=1.2,  # GA preenchido abaixo
            xg_por_jogo=xg,
        )

    # gols sofridos (GA) e xGA vem na tabela "against" do FBref (opponent stats)
    try:
        contra = fb.read_team_season_stats(stat_type="standard", opponent_stats=True)
        contra = contra.reset_index()
        contra.columns = ["_".join([str(c) for c in col if str(c) != ""]).strip("_")
                          if isinstance(col, tuple) else str(col) for col in contra.columns]
        c_time = achar(contra, "team") or "team"
        c_ga = achar(contra, "performance", "gls") or achar(contra, "_gls")
        c_xga = achar(contra, "expected", "xg") or achar(contra, "_xg")
        c_mp = achar(contra, "mp")
        for _, r in contra.iterrows():
            nome = str(r[c_time])
            if nome in times:
                jogos = float(r[c_mp]) or 1
                if c_ga:
                    times[nome].gols_sofridos_por_jogo = float(r[c_ga]) / jogos
                if c_xga:
                    times[nome].xga_por_jogo = float(r[c_xga]) / jogos
    except Exception:
        pass

    if not times:
        raise RuntimeError("FBref nao retornou times (estrutura inesperada ou bloqueio).")
    return times


def carregar_estatisticas(liga_key: str, usar_fbref: bool = True) -> dict[str, EstatisticasTime]:
    """
    Funcao principal: devolve {nome_time: EstatisticasTime}.
    Tenta FBref; se falhar, cai no CSV. Sempre salva cache quando o FBref funciona.
    """
    if usar_fbref:
        try:
            times = buscar_fbref(liga_key)
            salvar_times_csv(liga_key, times)
            print(f"  [FBref OK] {len(times)} times de {LIGAS[liga_key]['nome']}")
            return times
        except Exception as e:
            print(f"  [FBref falhou: {type(e).__name__}] usando CSV salvo. ({e})")

    times = carregar_times_csv(liga_key)
    if times:
        print(f"  [CSV] {len(times)} times de {LIGAS[liga_key]['nome']}")
    else:
        print(f"  [SEM DADOS] {LIGAS[liga_key]['nome']} - preencha {_caminho_csv(liga_key).name}")
    return times
