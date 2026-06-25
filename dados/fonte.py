"""
Cache CSV das estatisticas de cada time (backup quando o 365scores falha).

A coleta REAL vem de dados/scores365.py. Aqui so salvamos/lemos o ultimo
resultado bem-sucedido num CSV, que tambem pode ser editado a mao no Excel.

Colunas do CSV de times (medias POR JOGO):
  time, jogos, gols_feitos, gols_sofridos, xg, xga, esc_feitos, esc_sofridos, cartoes
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PASTA_DADOS  # noqa: E402
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
