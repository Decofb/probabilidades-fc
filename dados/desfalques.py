"""
DESFALQUES  ->  suspensos e lesionados de cada time por rodada.

Fonte principal: GE Globo / Cartola — artigo consolidado publicado ~5 dias antes
de cada rodada com suspensos, lesionados e prováveis de todos os 20 times.

Fluxo:
  1. Detecta a rodada atual pelo Flashscore (campo ER÷ nos fixtures).
  2. Tenta encontrar o artigo do GE Cartola (retroage até 45 dias na URL).
  3. Parseia com BeautifulSoup + regex — formato é consistente.
  4. Cacheia em cache/desfalques/ por 12h (artigo é atualizado até véspera).

Saída de coletar_desfalques(liga_key):
    {
      "flamengo": {
          "suspensos": ["Pedro"],
          "lesionados": ["Arrascaeta", "Gerson"],
          "duvidas": [],
          "provavel": "Rossi; Wesley, ...",
      },
      ...
    }
    Nomes normalizados (unidecode + lower) para facilitar lookup.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PASTA_CACHE  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Configuração ──────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

CACHE_DIR = PASTA_CACHE / "desfalques"
CACHE_TTL = 12 * 3600  # 12h — artigo é atualizado até véspera

# Dias para retroagir procurando o artigo (artigos saem ~5 dias antes da rodada)
DIAS_BUSCA = 45

# URL base do GE Cartola (Série A e B)
GE_URL_TEMPLATE = (
    "https://ge.globo.com/cartola/noticia/{ano}/{mes:02d}/{dia:02d}/"
    "cartola-{ano}-veja-suspensos-lesionados-e-escalacoes-provaveis-"
    "da-rodada-{rodada}-do-brasileirao.ghtml"
)

# Padrões de seção por time no texto do artigo
_RE_TIME = re.compile(r'^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\-\./ ]{2,})$')
_RE_SUSPENSOS = re.compile(r'[Ss]uspensos?\s*[:：]\s*(.+)')
_RE_LESIONADOS = re.compile(r'[Ll]esionados?\s*[:：]\s*(.+)')
_RE_DUVIDAS = re.compile(r'[Dd]úvidas?\s*[:：]\s*(.+)|[Dd]uvidas?\s*[:：]\s*(.+)')
_RE_PROVAVEL = re.compile(r'[Tt]ime\s+prováve[l]?\s*[:：]\s*(.+)|'
                           r'[Ee]scala[çc][aã]o\s+prováve[l]?\s*[:：]\s*(.+)')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return unidecode(s or "").lower().strip()


def _split_jogadores(s: str) -> list[str]:
    """'Pedro, Arrascaeta e Gerson' → ['Pedro', 'Arrascaeta', 'Gerson']"""
    s = s.strip()
    if not s or _norm(s) in ("ninguem", "nenhum", "-", "—"):
        return []
    # Separa por vírgula e 'e'
    nomes = re.split(r",\s*|\s+e\s+", s)
    return [n.strip() for n in nomes if n.strip() and len(n.strip()) > 2]


# ── Detecção da rodada atual ──────────────────────────────────────────────────

def rodada_atual(liga_key: str) -> Optional[int]:
    """
    Detecta a rodada atual via Flashscore (campo ER÷ nos fixtures e resultados).
    Retorna o maior número de rodada encontrado nos jogos recentes.
    """
    try:
        from dados.flashscore import _fetch, _extrair_blocos, _URLS
        urls = _URLS.get(liga_key, {})
        # Tenta fixtures primeiro (jogos futuros)
        for tipo in ("fixtures", "resultados"):
            url = urls.get(tipo)
            if not url:
                continue
            html = _fetch(url, liga_key, tipo, usar_cache=True)
            blocos = _extrair_blocos(html)
            rodadas = []
            for b in blocos:
                er = b.get("ER", "")
                m = re.search(r'\d+', er)
                if m:
                    rodadas.append(int(m.group()))
            if rodadas:
                return max(rodadas)
    except Exception:
        pass
    return None


# ── Busca do artigo GE Cartola ────────────────────────────────────────────────

def _url_ge(rodada: int, d: date) -> str:
    return GE_URL_TEMPLATE.format(
        ano=d.year, mes=d.month, dia=d.day, rodada=rodada
    )


def buscar_artigo_ge(rodada: int, dias: int = DIAS_BUSCA) -> Optional[str]:
    """
    Procura o artigo do GE Cartola para a rodada N.
    Retroage até `dias` dias a partir de hoje.
    Retorna o HTML bruto ou None.
    """
    hoje = date.today()
    for delta in range(dias):
        d = hoje - timedelta(days=delta)
        url = _url_ge(rodada, d)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and len(r.text) > 50_000:
                print(f"  [desfalques] artigo GE rodada {rodada} em {d}: {url}")
                return r.text
        except Exception:
            pass
    return None


# ── Parser do artigo ──────────────────────────────────────────────────────────

def parsear_desfalques(html: str) -> dict[str, dict]:
    """
    Parseia o HTML do artigo GE Cartola.
    Retorna {nome_normalizado: {suspensos, lesionados, duvidas, provavel}}.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extrai texto de todas as tags <strong> — são os nomes de times (em caps)
    # e o texto que vem depois (suspensos, lesionados, etc.)
    # Pega o maior bloco de conteúdo
    content_divs = soup.find_all("div", class_=re.compile(r"content|article|body|texto", re.I))
    if not content_divs:
        return {}
    texto_principal = max(content_divs, key=lambda d: len(d.get_text())).get_text("\n", strip=True)

    resultado: dict[str, dict] = {}
    time_atual = None
    dados: dict = {}

    # Divisão por linhas — each <strong> com nome em caps é um novo time
    for linha in texto_principal.split("\n"):
        linha = linha.strip()
        if not linha:
            continue

        # Novo time? (texto em maiúsculas, sem números)
        if _RE_TIME.match(linha) and len(linha) <= 40 and not any(c.isdigit() for c in linha):
            # Salva time anterior
            if time_atual and dados:
                resultado[_norm(time_atual)] = dados
            time_atual = linha
            dados = {
                "time_original": linha,
                "suspensos": [],
                "lesionados": [],
                "duvidas": [],
                "provavel": "",
            }
            continue

        if time_atual is None:
            continue

        # Suspensos
        m = _RE_SUSPENSOS.match(linha)
        if m:
            dados["suspensos"] = _split_jogadores(m.group(1))
            continue
        # Lesionados
        m = _RE_LESIONADOS.match(linha)
        if m:
            dados["lesionados"] = _split_jogadores(m.group(1))
            continue
        # Dúvidas
        m = _RE_DUVIDAS.match(linha)
        if m:
            texto_div = m.group(1) or m.group(2) or ""
            dados["duvidas"] = _split_jogadores(texto_div)
            continue
        # Provável
        m = _RE_PROVAVEL.match(linha)
        if m:
            dados["provavel"] = (m.group(1) or m.group(2) or "").strip()
            continue

    # Salva o último time
    if time_atual and dados:
        resultado[_norm(time_atual)] = dados

    return resultado


# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_path(liga_key: str, rodada: int) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{liga_key}_r{rodada}.json"


def _carregar_cache(liga_key: str, rodada: int) -> Optional[dict]:
    p = _cache_path(liga_key, rodada)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - d.get("ts", 0) < CACHE_TTL:
            return d.get("dados")
    except Exception:
        pass
    return None


def _salvar_cache(liga_key: str, rodada: int, dados: dict) -> None:
    p = _cache_path(liga_key, rodada)
    p.write_text(
        json.dumps({"ts": time.time(), "rodada": rodada, "dados": dados},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Interface pública ─────────────────────────────────────────────────────────

def coletar_desfalques(liga_key: str, usar_cache: bool = True) -> dict[str, dict]:
    """
    Coleta suspensos e lesionados da rodada atual para a liga.
    Retorna {nome_normalizado: {suspensos, lesionados, duvidas, provavel}}.
    Retorna {} se não conseguir dados.
    """
    # Só o Brasileirão tem cobertura no GE Cartola
    if liga_key not in ("brasileirao_a", "brasileirao_b"):
        return {}

    rodada = rodada_atual(liga_key)
    if rodada is None:
        print(f"  [desfalques] não conseguiu detectar rodada de {liga_key}")
        return {}

    # Tenta rodada atual e rodada+1 (artigo pode ser da rodada futura)
    for r in (rodada, rodada + 1, rodada - 1):
        if r <= 0:
            continue
        if usar_cache:
            cached = _carregar_cache(liga_key, r)
            if cached is not None:
                n_desfal = sum(
                    len(v.get("suspensos", [])) + len(v.get("lesionados", []))
                    for v in cached.values()
                )
                print(f"  [desfalques] cache rodada {r}: {len(cached)} times, {n_desfal} desfalques")
                return cached

        html = buscar_artigo_ge(r)
        if html:
            dados = parsear_desfalques(html)
            if dados:
                _salvar_cache(liga_key, r, dados)
                n_desfal = sum(
                    len(v.get("suspensos", [])) + len(v.get("lesionados", []))
                    for v in dados.values()
                )
                print(f"  [desfalques] rodada {r}: {len(dados)} times, {n_desfal} desfalques")
                return dados

    print(f"  [desfalques] artigo GE não encontrado para {liga_key}")
    return {}


def _core_nome(s: str) -> str:
    """Remove siglas de estado ao final (MG, SP, RJ…) e hífens — para cross-matching."""
    s = re.sub(r'[-_]?[A-Z]{2}$', '', s.strip())
    return re.sub(r'[-_]', ' ', s).strip()


def desfalques_do_jogo(mandante: str, visitante: str,
                       dados: dict[str, dict]) -> dict:
    """
    Retorna os desfalques dos dois times de um jogo específico.
    {
      "mandante": {"suspensos": [...], "lesionados": [...], "duvidas": [...]},
      "visitante": {...},
      "tem_desfalque": bool,
    }
    """
    def buscar(nome: str) -> dict:
        import difflib
        norm = _norm(nome)
        chaves = list(dados.keys())

        # 1) Exato
        if norm in dados:
            return dados[norm]

        # 2) Fuzzy direto (nomes similares sem abreviação)
        match = difflib.get_close_matches(norm, chaves, n=1, cutoff=0.72)
        if match:
            return dados[match[0]]

        # 3) Fuzzy sem sigla de estado (Atlético Mineiro → atletico ≈ atletico)
        core = _norm(_core_nome(norm))
        cores_chave = {_norm(_core_nome(k)): k for k in chaves}
        if core in cores_chave:
            return dados[cores_chave[core]]
        match2 = difflib.get_close_matches(core, list(cores_chave.keys()), n=1, cutoff=0.72)
        if match2:
            return dados[cores_chave[match2[0]]]

        return {"suspensos": [], "lesionados": [], "duvidas": [], "provavel": ""}

    dm = buscar(mandante)
    dv = buscar(visitante)
    tem = bool(
        dm.get("suspensos") or dm.get("lesionados") or
        dv.get("suspensos") or dv.get("lesionados")
    )
    return {"mandante": dm, "visitante": dv, "tem_desfalque": tem}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Desfalques — suspensos e lesionados ===\n")
    for liga in ("brasileirao_a", "brasileirao_b"):
        print(f"\n--- {liga} ---")
        dados = coletar_desfalques(liga, usar_cache=False)
        for nome, d in sorted(dados.items())[:8]:
            sus = ", ".join(d["suspensos"]) or "—"
            les = ", ".join(d["lesionados"]) or "—"
            if d["suspensos"] or d["lesionados"]:
                print(f"  {d['time_original']:25s}  Susp: {sus}  |  Les: {les}")
    print()
