"""
Tabela de jogos (fixtures). Cada jogo: liga, data, hora, mandante, visitante.

A coleta REAL vem de dados/scores365.py (coletar_jogos_futuros). Aqui so
salvamos/lemos o cache CSV (backup), no formato:
  data (AAAA-MM-DD), hora, mandante, visitante, rodada
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PASTA_DADOS  # noqa: E402


@dataclass
class Jogo:
    liga_key: str
    data: str          # AAAA-MM-DD
    hora: str
    mandante: str
    visitante: str
    rodada: str = ""


def _caminho_csv(liga_key: str) -> Path:
    return PASTA_DADOS / f"{liga_key}_jogos.csv"


def salvar_jogos_csv(liga_key: str, jogos: list[Jogo]) -> Path:
    caminho = _caminho_csv(liga_key)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data", "hora", "mandante", "visitante", "rodada"])
        for j in jogos:
            w.writerow([j.data, j.hora, j.mandante, j.visitante, j.rodada])
    return caminho


def carregar_jogos_csv(liga_key: str) -> list[Jogo]:
    caminho = _caminho_csv(liga_key)
    if not caminho.exists():
        return []
    jogos = []
    with caminho.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            jogos.append(Jogo(
                liga_key=liga_key,
                data=row.get("data", "").strip(),
                hora=row.get("hora", "").strip(),
                mandante=row.get("mandante", "").strip(),
                visitante=row.get("visitante", "").strip(),
                rodada=row.get("rodada", "").strip(),
            ))
    return [j for j in jogos if j.mandante and j.visitante]
