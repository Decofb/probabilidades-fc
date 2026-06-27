"""
FLASHSCORE  ->  fonte alternativa de resultados para cross-validação.

Acessa a versão estática do site (HTTP puro, sem Playwright):
  - resultados passados: gols por jogo → médias por time
  - jogos futuros: data, horário, mandante, visitante

Limitações conhecidas:
  - xG, escanteios e cartões NÃO estão no HTML inicial (carregados via JS).
    Os campos ficam como None no EstatisticasTime.
  - Usa resultados de uma única página (~últimos 50 jogos por competição).

Cache: cada página tem TTL de 3 horas (resultados mudam pouco, jogos futuros mudam mais).
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PASTA_CACHE, PASTA_DADOS  # noqa: E402
from motor.forca import EstatisticasTime  # noqa: E402
from dados.jogos import Jogo  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Configuração ────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# URLs de resultados e tabela por competição
_URLS = {
    "brasileirao_a": {
        "resultados": "https://www.flashscore.com.br/futebol/brasil/brasileirao-betano/resultados/",
        "fixtures":   "https://www.flashscore.com.br/futebol/brasil/brasileirao-betano/",
    },
    "brasileirao_b": {
        "resultados": "https://www.flashscore.com.br/futebol/brasil/serie-b/resultados/",
        "fixtures":   "https://www.flashscore.com.br/futebol/brasil/serie-b/",
    },
    "copa_mundo": {
        "resultados": "https://www.flashscore.com.br/futebol/mundo/copa-do-mundo-fifa/resultados/",
        "fixtures":   "https://www.flashscore.com.br/futebol/mundo/copa-do-mundo-fifa/",
    },
}

CACHE_DIR = PASTA_CACHE / "flashscore"
CACHE_TTL = 3 * 3600  # 3 horas

# Status Flashscore: 1=não iniciado, 2=em andamento, 3=finalizado
STATUS_FINALIZADO = "3"
STATUS_NAO_INICIADO = "1"


# ── Parser ¬-delimitado ──────────────────────────────────────────────────────

def _parse_block(raw: str) -> dict[str, str]:
    """
    Parseia um bloco ~AA÷{id}¬field÷value¬... em dict.
    O match_id é extraído da parte antes do primeiro ¬.
    """
    parts = re.split(r'¬([A-Z]{2,3})÷', raw)
    d: dict[str, str] = {}
    if parts:
        # Primeira parte: o próprio match_id (antes de qualquer ¬)
        d["AA"] = parts[0].split("¬")[0].strip()
    for i in range(1, len(parts) - 1, 2):
        chave = parts[i]
        valor = parts[i + 1].split("¬")[0] if "¬" in parts[i + 1] else parts[i + 1]
        d[chave] = valor.strip()
    return d


def _extrair_blocos(html: str) -> list[dict[str, str]]:
    """Divide o HTML pelos separadores ~AA÷ e parseia cada bloco."""
    partes = html.split("~AA÷")
    blocos = []
    for raw in partes[1:]:
        b = _parse_block(raw)
        if b.get("AA"):
            blocos.append(b)
    return blocos


# ── Cache HTTP ────────────────────────────────────────────────────────────────

def _cache_path(comp_key: str, tipo: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{comp_key}_{tipo}.json"


def _carregar_cache(comp_key: str, tipo: str) -> Optional[str]:
    p = _cache_path(comp_key, tipo)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        gerado = d.get("ts", 0)
        if (time.time() - gerado) < CACHE_TTL:
            return d.get("html")
    except Exception:
        pass
    return None


def _salvar_cache(comp_key: str, tipo: str, html: str) -> None:
    p = _cache_path(comp_key, tipo)
    p.write_text(
        json.dumps({"ts": time.time(), "html": html}, ensure_ascii=False),
        encoding="utf-8",
    )


def _fetch(url: str, comp_key: str, tipo: str, usar_cache: bool = True) -> str:
    if usar_cache:
        cached = _carregar_cache(comp_key, tipo)
        if cached is not None:
            return cached
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    html = r.text
    _salvar_cache(comp_key, tipo, html)
    return html


# ── API pública ──────────────────────────────────────────────────────────────

def coletar_estatisticas(
    comp_key: str,
    d1: str = "",
    d2: str = "",
    max_jogos: int = 120,
    usar_cache: bool = True,
) -> dict[str, EstatisticasTime]:
    """
    Coleta resultados passados do Flashscore e agrega médias por time.

    Retorna dict[nome_time → EstatisticasTime] com:
      - gols_feitos_por_jogo / gols_sofridos_por_jogo  (disponíveis)
      - xg_por_jogo / xga_por_jogo                     (None — carregado via JS)
      - escanteios / cartões                            (None — carregado via JS)

    d1/d2 são ignorados (Flashscore entrega a página com histórico recente).
    Use max_jogos para limitar o número de partidas consideradas.
    """
    urls = _URLS.get(comp_key)
    if not urls:
        print(f"  [flashscore] competição desconhecida: {comp_key}")
        return {}

    try:
        html = _fetch(urls["resultados"], comp_key, "resultados", usar_cache)
    except Exception as e:
        print(f"  [flashscore] erro ao buscar {comp_key}: {e}")
        return {}

    blocos = _extrair_blocos(html)
    finalizados = [b for b in blocos if b.get("AB") == STATUS_FINALIZADO]
    finalizados = finalizados[-max_jogos:]  # últimos N jogos

    acc: dict[str, dict] = {}

    def garante(nome: str) -> dict:
        acc.setdefault(nome, dict(jogos=0, gf=0.0, gs=0.0))
        return acc[nome]

    for b in finalizados:
        home = b.get("AF", "").strip()
        away = b.get("AE", "").strip()
        gh_s = b.get("AH", "")
        ga_s = b.get("AG", "")
        if not home or not away or not gh_s or not ga_s:
            continue
        try:
            gh, ga = float(gh_s), float(ga_s)
        except ValueError:
            continue

        H, A = garante(home), garante(away)
        H["jogos"] += 1;  A["jogos"] += 1
        H["gf"] += gh;    H["gs"] += ga
        A["gf"] += ga;    A["gs"] += gh

    times: dict[str, EstatisticasTime] = {}
    for nome, a in acc.items():
        j = a["jogos"]
        if j == 0:
            continue
        times[nome] = EstatisticasTime(
            nome=nome,
            jogos=j,
            gols_feitos_por_jogo=round(a["gf"] / j, 3),
            gols_sofridos_por_jogo=round(a["gs"] / j, 3),
            xg_por_jogo=None,
            xga_por_jogo=None,
            escanteios_feitos_por_jogo=None,
            escanteios_sofridos_por_jogo=None,
            cartoes_por_jogo=None,
        )

    print(f"  [flashscore] {comp_key}: {len(finalizados)} jogos → {len(times)} times")
    return times


def coletar_jogos_futuros(
    comp_key: str,
    liga_key: str,
    d1: str = "",
    d2: str = "",
    usar_cache: bool = True,
) -> list[Jogo]:
    """
    Retorna próximos jogos (não iniciados) da competição.

    d1/d2 são ignorados — Flashscore retorna o que estiver na página de fixtures.
    """
    urls = _URLS.get(comp_key)
    if not urls:
        return []

    try:
        html = _fetch(urls["fixtures"], comp_key, "fixtures", usar_cache)
    except Exception as e:
        print(f"  [flashscore] erro ao buscar fixtures {comp_key}: {e}")
        return []

    blocos = _extrair_blocos(html)
    futuros = [b for b in blocos if b.get("AB") == STATUS_NAO_INICIADO]

    jogos: list[Jogo] = []
    for b in futuros:
        home = b.get("AF", "").strip()
        away = b.get("AE", "").strip()
        ts_s = b.get("AD", "")
        rodada = b.get("ER", "").strip()
        if not home or not away or not ts_s:
            continue
        try:
            ts = int(ts_s)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            # Converte para horário de Brasília (UTC-3)
            from datetime import timedelta
            dt_br = dt - timedelta(hours=3)
            data = dt_br.strftime("%Y-%m-%d")
            hora = dt_br.strftime("%H:%M")
        except Exception:
            data, hora = "", ""

        jogos.append(Jogo(
            liga_key=liga_key,
            data=data,
            hora=hora,
            mandante=home,
            visitante=away,
            rodada=rodada,
        ))

    print(f"  [flashscore] {comp_key} fixtures: {len(jogos)} jogos futuros")
    return jogos


def comparar_com_365(
    flash: dict[str, EstatisticasTime],
    s365: dict[str, EstatisticasTime],
    limiar_delta: float = 0.3,
) -> list[dict]:
    """
    Compara médias de gols entre Flashscore e 365scores.
    Retorna lista de divergências acima do limiar (gols por jogo).

    Útil para detectar nomes de times diferentes ou erros nos dados.
    """
    import difflib

    divergencias = []

    def melhor_match(nome: str, candidatos: list[str]) -> Optional[str]:
        matches = difflib.get_close_matches(nome.lower(), [c.lower() for c in candidatos],
                                             n=1, cutoff=0.7)
        if not matches:
            return None
        idx = [c.lower() for c in candidatos].index(matches[0])
        return candidatos[idx]

    nomes_365 = list(s365.keys())
    for nome_flash, ef in flash.items():
        nome_365 = melhor_match(nome_flash, nomes_365)
        if nome_365 is None:
            continue
        e365 = s365[nome_365]
        delta_gf = abs(ef.gols_feitos_por_jogo - e365.gols_feitos_por_jogo)
        delta_gs = abs(ef.gols_sofridos_por_jogo - e365.gols_sofridos_por_jogo)
        if delta_gf > limiar_delta or delta_gs > limiar_delta:
            divergencias.append({
                "time_flash": nome_flash,
                "time_365": nome_365,
                "flash_gf": round(ef.gols_feitos_por_jogo, 2),
                "s365_gf": round(e365.gols_feitos_por_jogo, 2),
                "flash_gs": round(ef.gols_sofridos_por_jogo, 2),
                "s365_gs": round(e365.gols_sofridos_por_jogo, 2),
                "delta_gf": round(delta_gf, 2),
                "delta_gs": round(delta_gs, 2),
            })

    divergencias.sort(key=lambda d: -(d["delta_gf"] + d["delta_gs"]))
    return divergencias


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Flashscore — resultados e estatísticas ===\n")
    for comp in ("brasileirao_a", "brasileirao_b"):
        print(f"\n--- {comp} ---")
        times = coletar_estatisticas(comp, usar_cache=False)
        for nome, e in sorted(times.items())[:8]:
            print(f"  {nome}: {e.jogos}j  GF={e.gols_feitos_por_jogo:.2f}  "
                  f"GS={e.gols_sofridos_por_jogo:.2f}")
        print(f"\n  Próximos jogos:")
        futuros = coletar_jogos_futuros(comp, comp, usar_cache=False)
        for j in futuros[:5]:
            print(f"    {j.data} {j.hora}  {j.mandante} vs {j.visitante}  [{j.rodada}]")
