"""
Registro de previsoes ao vivo (log forward, out-of-sample de verdade).

Todo dia a atualizacao salva o que o modelo previu para os jogos do dia.
Quando o jogo termina, conferir.py preenche o resultado real. O relatorio.py
le os conferidos e mede a calibracao no mundo real, ao longo das rodadas.

Arquivo: dados/previsoes_log.csv (uma linha por jogo, versionado no git).
"""

from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unidecode import unidecode  # noqa: E402

from config import PASTA_DADOS  # noqa: E402

CAMINHO = PASTA_DADOS / "previsoes_log.csv"

COLS = ["id", "registrado_em", "liga", "data", "hora", "mandante", "visitante",
        "p1", "px", "p2", "po05", "po15", "po25", "pbtts", "pesc95", "pcart45",
        "status", "gm", "gv", "corners", "cards", "conferido_em"]


def _norm(s: str) -> str:
    return unidecode(s or "").lower().strip()


def id_jogo(data: str, mandante: str, visitante: str) -> str:
    return f"{data}|{_norm(mandante)}|{_norm(visitante)}"


def carregar() -> list[dict]:
    if not CAMINHO.exists():
        return []
    with CAMINHO.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _salvar(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: (r.get("data", ""), r.get("hora", ""), r.get("id", "")))
    with CAMINHO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})


def registrar(novas: list[dict]) -> int:
    """
    Insere/atualiza previsoes (chave = id). Nao toca em jogos ja CONFERIDOS
    (preserva a previsao pre-jogo original). Devolve quantas foram gravadas.
    """
    rows = {r["id"]: r for r in carregar()}
    gravadas = 0
    for nv in novas:
        ex = rows.get(nv["id"])
        if ex and ex.get("status") == "conferido":
            continue
        rows[nv["id"]] = {**(ex or {}), **nv}
        gravadas += 1
    _salvar(list(rows.values()))
    return gravadas


def pendentes(hoje_str: str) -> list[dict]:
    """Previsoes nao conferidas cujo jogo e de hoje ou ja passou (data <= hoje).
    Inclui hoje p/ conciliar jogos que ja terminaram no mesmo dia."""
    return [r for r in carregar()
            if r.get("status") == "previsto" and r.get("data", "") <= hoje_str]


def conferidos() -> list[dict]:
    """Jogos ja conciliados com resultado real, mais recentes primeiro."""
    rows = [r for r in carregar() if r.get("status") == "conferido"
            and r.get("gm", "") != "" and r.get("gv", "") != ""]
    return sorted(rows, key=lambda r: (r.get("data", ""), r.get("hora", "")), reverse=True)


def expirar(hoje_str: str, dias: int = 10) -> int:
    """
    Marca como 'expirado' previsoes que continuam 'previsto' mas cujo jogo ja
    passou ha mais de 'dias' (provavelmente adiado/cancelado). Evita consultar
    pra sempre e mantem o log limpo.
    """
    try:
        limite = (date.fromisoformat(hoje_str) - timedelta(days=dias)).isoformat()
    except ValueError:
        return 0
    rows = carregar()
    n = 0
    for r in rows:
        if r.get("status") == "previsto" and r.get("data", "") and r["data"] < limite:
            r["status"] = "expirado"
            n += 1
    if n:
        _salvar(rows)
    return n


def conferir(resultados: dict, conferido_em: str) -> int:
    """
    resultados = {id: (gm, gv, corners, cards)}. Preenche o resultado real nas
    previsoes pendentes e marca como conferido. Devolve quantas foram conferidas.
    """
    rows = carregar()
    n = 0
    for r in rows:
        if r.get("status") == "previsto" and r["id"] in resultados:
            gm, gv, corners, cards = resultados[r["id"]]
            r.update(gm=gm, gv=gv, corners=corners, cards=cards,
                     status="conferido", conferido_em=conferido_em)
            n += 1
    if n:
        _salvar(rows)
    return n
