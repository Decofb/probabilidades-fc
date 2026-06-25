"""
Tabela de jogos (fixtures). Cada jogo: liga, data, hora, mandante, visitante.

Fontes:
  - CSV editavel {liga}_jogos.csv  -> base oficial (voce cola da FIFA.com / ge.globo)
  - FBref schedule                 -> reforco automatico quando disponivel

CSV de jogos (colunas): data, hora, mandante, visitante, rodada
  data no formato AAAA-MM-DD
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PASTA_DADOS, LIGAS  # noqa: E402


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


def carregar_jogos(liga_key: str) -> list[Jogo]:
    """Por enquanto: CSV (FIFA/ge.globo). FBref schedule pode ser plugado depois."""
    return carregar_jogos_csv(liga_key)


def todos_os_jogos() -> list[Jogo]:
    todos = []
    for k in LIGAS:
        todos.extend(carregar_jogos(k))
    return sorted(todos, key=lambda j: (j.data, j.hora))
