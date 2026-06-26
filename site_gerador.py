"""
Gera o site (docs/index.html): um "instrumento de probabilidade" para futebol.
Conceito: terminal de analise (nao site de aposta). Numeros em mono, barra de
forca 1X2 como assinatura de cada jogo, tipografia Space Grotesk + IBM Plex Mono.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import PASTA_SITE  # noqa: E402
from dados.jogos import Jogo  # noqa: E402
from motor.poisson import ResultadoMercados  # noqa: E402


def _nav(ativo: str) -> str:
    itens = [("index.html", "⚽ Jogos", "jogos"), ("dicas.html", "💡 Dicas", "dicas"),
             ("tendencias.html", "📊 Tendências", "tend"), ("historico.html", "📅 Histórico", "hist")]
    links = "".join(f'<a class="{"on" if k == ativo else ""}" href="{href}">{txt}</a>'
                    for href, txt, k in itens)
    return f'<nav class="nav">{links}</nav>'


def _tom(pct: int) -> str:
    """Esmeralda com intensidade proporcional ao % (barras secundarias)."""
    a = 0.30 + 0.62 * (max(0, min(pct, 100)) / 100)
    return f"rgba(52,226,160,{round(a, 2)})"


def _melhor_aposta(j: Jogo, m: ResultadoMercados) -> tuple[str, int]:
    """Mercado AFIRMATIVO de maior probabilidade (sem complementares triviais)."""
    candidatos = [
        (f"Vitória {j.mandante}", m.pct(m.vitoria_mandante)),
        ("Empate", m.pct(m.empate)),
        (f"Vitória {j.visitante}", m.pct(m.vitoria_visitante)),
        ("Over 2.5 gols", m.pct(m.over_25)),
        ("Ambas marcam", m.pct(m.ambas_marcam)),
    ]
    return max(candidatos, key=lambda c: c[1])


def _mercado(label: str, pct: int) -> str:
    """Uma linha de mercado: rotulo · barra (intensidade) · valor em mono."""
    return (f'<div class="m"><span class="m-lbl">{label}</span>'
            f'<span class="m-track"><span class="fill" style="--w:{pct}%;background:{_tom(pct)}"></span></span>'
            f'<span class="m-val">{pct}<i>%</i></span></div>')


def _bloco(titulo: str, extra: str, linhas: str) -> str:
    extra_html = f'<span class="eyebrow-x">{extra}</span>' if extra else ""
    return (f'<div class="bloco"><div class="eyebrow">{titulo}{extra_html}</div>{linhas}</div>')


def card_jogo(j: Jogo, m: ResultadoMercados, liga_cfg: dict | None = None) -> str:
    nome_m = html.escape(j.mandante)
    nome_v = html.escape(j.visitante)
    pm, pe, pv = m.pct(m.vitoria_mandante), m.pct(m.empate), m.pct(m.vitoria_visitante)

    aposta, conf = _melhor_aposta(j, m)
    aposta = html.escape(aposta)

    selo = ""
    if liga_cfg:
        selo = f'{liga_cfg.get("emoji", "")} {html.escape(liga_cfg.get("nome", ""))}'
    hora = html.escape(j.hora or "")

    # bloco gols
    gols = (_mercado("+0.5 gols", m.pct(m.over_05)) + _mercado("+1.5 gols", m.pct(m.over_15)) +
            _mercado("+2.5 gols", m.pct(m.over_25)) + _mercado("Ambas marcam", m.pct(m.ambas_marcam)))
    blocos = _bloco("Gols", "total da partida", gols)

    # Handicap asiático foi removido a pedido (pouca utilidade percebida).
    # Escanteios e cartoes NAO sao exibidos: o backtest mostrou que nao superam
    # o baseline. Continuam sendo calculados e logados (registro) para reavaliacao
    # futura, mas ficam fora do site enquanto nao forem calibrados.

    return f"""
    <article class="card">
      <div class="card-top">
        <span class="liga-tag">{selo}</span>
        <span class="hora">{hora}</span>
      </div>
      <div class="match">
        <span class="team">{nome_m}</span><span class="vs">vs</span><span class="team">{nome_v}</span>
      </div>

      <div class="forca" role="img" aria-label="{nome_m} {pm}%, empate {pe}%, {nome_v} {pv}%">
        <span class="seg seg-m" style="--w:{pm}%"></span>
        <span class="seg seg-e" style="--w:{pe}%"></span>
        <span class="seg seg-v" style="--w:{pv}%"></span>
      </div>
      <div class="leg">
        <div class="leg-i leg-m"><span class="leg-p">{pm}<i>%</i></span><span class="leg-n">{nome_m}</span></div>
        <div class="leg-i leg-e"><span class="leg-p">{pe}<i>%</i></span><span class="leg-n">Empate</span></div>
        <div class="leg-i leg-v"><span class="leg-p">{pv}<i>%</i></span><span class="leg-n">{nome_v}</span></div>
      </div>

      <div class="leitura">
        <span class="leitura-tag">Leitura</span>
        <span class="leitura-val">{aposta}</span>
        <span class="leitura-pct">{conf}%</span>
      </div>

      {blocos}

      <div class="readout">
        <span>Placar provável <b>{m.placar_provavel[0]}–{m.placar_provavel[1]}</b> · {m.pct(m.prob_placar_provavel)}%</span>
        <span>xG <b>{m.gols_esperados_mandante:.1f}</b> · <b>{m.gols_esperados_visitante:.1f}</b></span>
      </div>
    </article>"""


def gerar_site(grupos_data: list[tuple[str, str, list[str]]], data_geracao: str,
               dados_backup: bool = False, placar: str = "") -> Path:
    """grupos_data = lista ordenada de (rotulo, subtitulo, [html_card, ...])."""
    nomes = {"HOJE": "Hoje", "AMANHÃ": "Amanhã"}
    secoes = ""
    for rotulo, subtitulo, cards in grupos_data:
        if not cards:
            continue
        titulo = nomes.get(rotulo, rotulo)
        cls = "daymark hoje" if rotulo == "HOJE" else "daymark"
        n = len(cards)
        secoes += f"""
      <section>
        <div class="{cls}">
          <span class="day">{titulo}</span>
          <span class="day-sub">{subtitulo}</span>
          <span class="rule"></span>
          <span class="day-count">{n} jogo{'s' if n != 1 else ''}</span>
        </div>
        <div class="grade">{''.join(cards)}</div>
      </section>"""

    if not secoes:
        secoes = '<p class="vazio">Nenhum jogo para hoje ou amanhã no momento.</p>'

    if (PASTA_SITE / "logo.png").exists():
        marca = '<img class="logo-full" src="logo.png" alt="Probabilidades FC">'
    else:
        marca = '<h1>Probabilidades FC</h1>'

    backup = ""
    if dados_backup:
        backup = ('<div class="backup">Dados de backup — a coleta de hoje não rodou; '
                  'mostrando a última atualização bem-sucedida.</div>')

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#090d13">
<meta name="description" content="Probabilidades de futebol por estatística — sem odds. Copa do Mundo e Brasileirão.">
<title>Probabilidades FC</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
  :root {{
    --ink:#090d13; --panel:#0c121c; --panel2:#0a0f17;
    --line:#1a2433; --line2:#131b27;
    --bone:#e9ede9; --mut:#8593a3; --faint:#566678;
    --em:#34e2a0; --em-soft:#1e8f66; --amber:#f1b24a; --slate:#5d6e84;
    --r:14px;
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{ margin:0; color:var(--bone); font-family:'Hanken Grotesk',system-ui,sans-serif;
    background:
      radial-gradient(900px 480px at 50% -260px,#11251c 0%,transparent 62%),
      radial-gradient(720px 420px at 100% -80px,#0e1a2a 0%,transparent 60%),
      var(--ink);
    background-attachment:fixed; -webkit-font-smoothing:antialiased; }}
  ::selection {{ background:var(--em); color:#04130d; }}

  header {{ text-align:center; padding:42px 18px 26px; }}
  .brand {{ display:flex; justify-content:center; align-items:center; }}
  .brand .logo-full {{ height:78px; max-width:86vw; object-fit:contain;
    filter:drop-shadow(0 8px 26px rgba(52,226,160,.16)); }}
  .brand h1 {{ margin:0; font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:30px; color:var(--bone); }}
  .tagline {{ margin-top:13px; font-size:14px; color:var(--mut); letter-spacing:.2px; }}
  .tagline b {{ color:var(--bone); font-weight:600; }}
  .status {{ margin-top:10px; font-family:'IBM Plex Mono',monospace; font-size:10.5px;
    text-transform:uppercase; letter-spacing:1.6px; color:var(--faint);
    display:flex; gap:10px; justify-content:center; align-items:center; flex-wrap:wrap; }}
  .status b {{ color:var(--em); font-weight:500; }}
  .dot {{ width:3px; height:3px; border-radius:50%; background:var(--faint); }}
  .nota {{ max-width:680px; margin:18px auto 0; font-size:11.5px; line-height:1.55; color:var(--faint);
    border-left:2px solid var(--em-soft); padding-left:13px; text-align:left; }}
  .backup {{ max-width:680px; margin:14px auto 0; padding:9px 14px; border-radius:10px; text-align:center;
    font-size:12.5px; color:#ffdada; background:rgba(220,40,40,.12); border:1px solid rgba(220,40,40,.35); }}

  .nav {{ display:flex; flex-wrap:wrap; justify-content:center; gap:8px; padding:16px 16px 0; }}
  .nav a {{ font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.5px; text-decoration:none;
    color:var(--mut); padding:7px 16px; border:1px solid var(--line); border-radius:999px; transition:all .15s; }}
  .nav a.on {{ color:#04130d; background:var(--em); border-color:var(--em); font-weight:600; }}
  .nav a:hover {{ border-color:var(--em); color:var(--bone); }}

  main {{ max-width:1000px; margin:0 auto; padding:6px 16px 84px; }}

  .daymark {{ display:flex; align-items:baseline; gap:13px; position:sticky; top:0; z-index:6;
    padding:18px 2px 13px; background:var(--ink);
    box-shadow:0 10px 18px -6px var(--ink), 0 1px 0 0 var(--line2); }}
  .day {{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:21px; letter-spacing:-.3px; color:var(--bone); }}
  .daymark.hoje .day {{ color:var(--em); }}
  .day-sub {{ font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:var(--mut); }}
  .rule {{ flex:1; height:1px; background:linear-gradient(90deg,var(--line),transparent); }}
  .day-count {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint); letter-spacing:.5px; }}

  .grade {{ display:grid; grid-template-columns:1fr; gap:14px; }}
  @media(min-width:760px) {{ .grade {{ grid-template-columns:1fr 1fr; }} }}

  .card {{ position:relative; background:linear-gradient(180deg,var(--panel),var(--panel2));
    border:1px solid var(--line); border-radius:var(--r); padding:15px 15px 13px;
    box-shadow:0 18px 40px -22px rgba(0,0,0,.8); transition:border-color .2s ease; }}
  .card:hover {{ border-color:#26344a; }}
  .card-top {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:9px; }}
  .liga-tag {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:1.2px;
    text-transform:uppercase; color:var(--mut); }}
  .hora {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint); letter-spacing:.5px; }}
  .match {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:14px; }}
  .team {{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16.5px; letter-spacing:-.2px; color:var(--bone); }}
  .vs {{ font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--faint); text-transform:uppercase; letter-spacing:1px; }}

  .forca {{ display:flex; height:12px; border-radius:7px; overflow:hidden; background:var(--line2); }}
  .seg {{ height:100%; width:var(--w); flex-shrink:0; animation:grow .85s cubic-bezier(.22,1,.36,1) both; }}
  .seg+.seg {{ margin-left:2px; }}
  .seg-m {{ background:linear-gradient(180deg,#43efb0,#22c98c); }}
  .seg-e {{ background:var(--slate); }}
  .seg-v {{ background:linear-gradient(180deg,#f6c265,#e0992f); }}
  .leg {{ display:flex; justify-content:space-between; margin-top:10px; gap:8px; }}
  .leg-i {{ display:flex; flex-direction:column; min-width:0; }}
  .leg-e {{ align-items:center; }} .leg-v {{ align-items:flex-end; }}
  .leg-p {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:18px; line-height:1; font-variant-numeric:tabular-nums; }}
  .leg-p i {{ font-style:normal; font-size:11px; color:var(--faint); margin-left:1px; }}
  .leg-m .leg-p {{ color:var(--em); }} .leg-e .leg-p {{ color:#aab6c6; }} .leg-v .leg-p {{ color:var(--amber); }}
  .leg-n {{ font-size:11px; color:var(--mut); margin-top:4px; max-width:130px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .leg-e .leg-n {{ text-align:center; }} .leg-v .leg-n {{ text-align:right; }}

  .leitura {{ display:flex; align-items:center; gap:10px; margin:15px 0 4px; padding:10px 13px;
    border:1px solid var(--line); border-left:2px solid var(--em); border-radius:10px;
    background:linear-gradient(90deg,rgba(52,226,160,.07),transparent); }}
  .leitura-tag {{ font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:1.4px; text-transform:uppercase; color:var(--faint); }}
  .leitura-val {{ font-weight:600; font-size:13.5px; color:var(--bone); }}
  .leitura-pct {{ margin-left:auto; font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:18px; color:var(--em); font-variant-numeric:tabular-nums; }}

  .bloco {{ margin-top:15px; }}
  .eyebrow {{ display:flex; align-items:baseline; gap:8px; font-family:'IBM Plex Mono',monospace;
    font-size:10px; letter-spacing:1.4px; text-transform:uppercase; color:var(--mut); margin-bottom:9px; }}
  .eyebrow-x {{ color:var(--faint); letter-spacing:.4px; text-transform:none; font-size:10.5px; }}
  .m {{ display:flex; align-items:center; gap:10px; margin:5px 0; }}
  .m-lbl {{ width:34%; font-size:12.5px; color:#c2cdda; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .m-track {{ flex:1; height:6px; border-radius:6px; background:var(--line2); overflow:hidden; }}
  .m-track .fill {{ display:block; height:100%; width:var(--w); border-radius:6px;
    animation:grow .85s cubic-bezier(.22,1,.36,1) both; }}
  .m-val {{ width:44px; text-align:right; font-family:'IBM Plex Mono',monospace; font-size:12.5px;
    font-weight:500; color:var(--bone); font-variant-numeric:tabular-nums; }}
  .m-val i {{ font-style:normal; color:var(--faint); font-size:10px; margin-left:1px; }}

  .readout {{ display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-top:14px; padding-top:12px;
    border-top:1px solid var(--line2); font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--faint); letter-spacing:.3px; }}
  .readout b {{ color:#c2cdda; font-weight:600; }}

  .vazio {{ text-align:center; color:var(--mut); margin-top:60px; }}
  .placar-cerebro {{ max-width:1000px; margin:14px auto 0; padding:13px 18px; text-align:center;
    font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:var(--mut); letter-spacing:.3px;
    line-height:1.6; border:1px solid var(--line); border-radius:12px; background:var(--panel2); }}
  footer {{ text-align:center; color:var(--faint); font-size:10.5px; padding:22px 16px;
    font-family:'IBM Plex Mono',monospace; letter-spacing:.4px; }}
  footer b {{ color:var(--em); font-weight:500; }}

  @keyframes grow {{ from {{ width:0; }} to {{ width:var(--w); }} }}
  @media(prefers-reduced-motion:reduce) {{ .seg, .m-track .fill {{ animation:none; }} }}
</style>
</head>
<body>
  {_nav("jogos")}
  <header>
    <div class="brand">{marca}</div>
    <div class="tagline">Probabilidades por estatística — <b>sem odds</b></div>
    <div class="status"><span>Poisson · Dixon-Coles</span><span class="dot"></span><span>Atualizado {data_geracao}</span></div>
    <div class="nota">Mostramos só os mercados validados por backtest (resultado, gols e ambas marcam) —
      escanteios e cartões saíram porque não superaram o palpite médio nos testes. As porcentagens são
      estimativas estatísticas (gols e xG do histórico recente); não são garantia — futebol tem zebra. Aposte com responsabilidade.</div>
    {backup}
  </header>
  <main>{secoes}</main>
  <div class="placar-cerebro">{html.escape(placar)}</div>
  <footer><b>Probabilidades FC</b> · modelo Poisson + Dixon-Coles · dados do 365scores</footer>
</body>
</html>"""

    destino = PASTA_SITE / "index.html"
    destino.write_text(html_doc, encoding="utf-8")
    return destino


# ===================== ABA TENDÊNCIAS =====================

def _amb_strip(a) -> str:
    if not a or a.get("n", 0) == 0:
        return ""
    cells = [("Gols/jogo", f"{a['gols_jogo']:.2f}"), ("Casa", f"{a['vit_casa']:.0f}%"),
             ("Empate", f"{a['empate']:.0f}%"), ("Fora", f"{a['vit_fora']:.0f}%"),
             ("Over 2.5", f"{a['o25']:.0f}%"), ("Ambas", f"{a['btts']:.0f}%")]
    if a.get("esc_jogo"):
        cells.append(("Escanteios", f"{a['esc_jogo']:.1f}"))
    if a.get("cart_jogo"):
        cells.append(("Cartões", f"{a['cart_jogo']:.1f}"))
    its = "".join(f'<div class="stat"><span class="stat-v">{v}</span><span class="stat-l">{l}</span></div>'
                  for l, v in cells)
    return f'<div class="ambiente">{its}</div>'


def _rank_card(titulo, sub, itens, fmt) -> str:
    if not itens:
        return ""
    lis = "".join(f'<li><span class="rk-n">{i}. {html.escape(n)}</span>'
                  f'<span class="rk-v">{fmt(v)}</span></li>' for i, (n, v) in enumerate(itens, 1))
    return (f'<div class="rcard"><div class="eyebrow">{titulo}'
            f'<span class="eyebrow-x">{sub}</span></div><ol class="rk">{lis}</ol></div>')


def _dna_card(t) -> str:
    xg = f" · xG {t['xg']:.2f}" if t.get("xg") else ""
    if t.get("flags"):
        flags = "".join(f'<span class="dna-flag">{f}</span>' for f in t["flags"])
        flags_html = f'<div class="dna-flags">{flags}</div>'
    else:
        flags_html = '<div class="dna-flags dim">sem padrão marcante</div>'
    return (f'<div class="dna-card"><div class="dna-top"><b>{html.escape(t["nome"])}</b>'
            f'<span class="dna-rec">{t["rec"]}</span></div>'
            f'<div class="dna-stats">⚔️ {t["gf"]:.2f}{xg} · 🛡️ {t["ga"]:.2f} · '
            f'O2.5 {t["over25"]:.0%} · BTTS {t["btts"]:.0%} · CS {t["cs"]:.0%}</div>{flags_html}</div>')


def gerar_tendencias(trends: list[dict], data_geracao: str) -> Path:
    """trends = lista de {nome, emoji, ambiente(dict estudar), rankings(dict)}."""
    secoes = ""
    for t in trends:
        r = t.get("rankings") or {}
        cards = ""
        if r:
            cards = (
                _rank_card("⚔️ Melhor ataque", "xG criado/jogo", r.get("ataque", []), lambda v: f"{v:.2f}") +
                _rank_card("🛡️ Melhor defesa", "xG sofrido/jogo", r.get("defesa", []), lambda v: f"{v:.2f}") +
                _rank_card("🍀 Azarados", "marcam menos que o xG · tendem a subir", r.get("azarados", []), lambda v: f"{v:+.2f}") +
                _rank_card("🎲 Sortudos", "marcam mais que o xG · tendem a cair", r.get("sortudos", []), lambda v: f"{v:+.2f}") +
                _rank_card("🔥 Mais over", "gols totais/jogo", r.get("over", []), lambda v: f"{v:.2f}") +
                _rank_card("🧱 Ferrolho", "menos gols totais/jogo", r.get("ferrolho", []), lambda v: f"{v:.2f}") +
                _rank_card("🟨 Mais cartões", "recebidos/jogo", r.get("cartoes", []), lambda v: f"{v:.1f}") +
                _rank_card("🏰 Fortes em casa", "% de vitória em casa", r.get("casa", []), lambda v: f"{v:.0%}"))

        sq = t.get("sequencias") or {}
        scards = ""
        if any(sq.values()):
            fj = lambda v: f"{int(v)} jogos"
            scards = (
                _rank_card("🛡️ Invictos", "jogos sem perder", sq.get("invicto", []), fj) +
                _rank_card("✅ Embalados", "vitórias seguidas", sq.get("vitorias", []), fj) +
                _rank_card("⚽ Marcando sempre", "jogos seguidos marcando", sq.get("marcando", []), fj) +
                _rank_card("🔒 Sem sofrer", "jogos seguidos sem levar gol", sq.get("clean", []), fj) +
                _rank_card("📈 Over em série", "jogos seguidos com +2.5", sq.get("over", []), fj) +
                _rank_card("🤝 BTTS em série", "jogos seguidos com ambas", sq.get("btts", []), fj))
        seq_html = f'<div class="subhead">🔥 Sequências quentes</div><div class="ranks">{scards}</div>' if scards else ""

        dna = t.get("dna") or []
        dna_html = ""
        if dna:
            cards_dna = "".join(_dna_card(x) for x in dna)
            dna_html = (f'<details class="padroes"><summary>🧬 Padrões de cada time ({len(dna)}) — clique para abrir</summary>'
                        f'<div class="dna-grid">{cards_dna}</div></details>')

        n = (t.get("ambiente") or {}).get("n", 0)
        scout = f'<div class="subhead">🕵️ Scout por xG</div><div class="ranks">{cards}</div>' if cards else ""
        secoes += f"""
      <section class="liga-sec">
        <h2><span>{t['emoji']}</span> {html.escape(t['nome'])}
            <span class="liga-n">{n} jogos disputados</span></h2>
        {_amb_strip(t.get('ambiente'))}
        {scout}
        {seq_html}
        {dna_html}
      </section>"""
    if not secoes:
        secoes = '<p class="vazio">Tendências em coleta…</p>'

    doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#090d13">
<title>Tendências · Probabilidades FC</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
  :root {{ --ink:#090d13; --panel:#0c121c; --panel2:#0a0f17; --line:#1a2433; --line2:#131b27;
    --bone:#e9ede9; --mut:#8593a3; --faint:#566678; --em:#34e2a0; --amber:#f1b24a; --r:14px; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; color:var(--bone); font-family:'Hanken Grotesk',system-ui,sans-serif;
    background: radial-gradient(900px 480px at 50% -260px,#11251c 0%,transparent 62%),
      radial-gradient(720px 420px at 100% -80px,#0e1a2a 0%,transparent 60%), var(--ink);
    background-attachment:fixed; -webkit-font-smoothing:antialiased; }}
  .nav {{ display:flex; flex-wrap:wrap; justify-content:center; gap:8px; padding:16px 16px 0; }}
  .nav a {{ font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.5px; text-decoration:none;
    color:var(--mut); padding:7px 16px; border:1px solid var(--line); border-radius:999px; }}
  .nav a.on {{ color:#04130d; background:var(--em); border-color:var(--em); font-weight:600; }}
  .nav a:hover {{ border-color:var(--em); color:var(--bone); }}
  header {{ text-align:center; padding:28px 18px 6px; }}
  header h1 {{ margin:0; font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:26px; }}
  header .sub {{ margin-top:8px; font-size:13px; color:var(--mut); }}
  header .ts {{ margin-top:6px; font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--faint);
    letter-spacing:1.4px; text-transform:uppercase; }}
  main {{ max-width:1120px; margin:0 auto; padding:10px 16px 80px; }}
  .liga-sec {{ margin-top:32px; }}
  .liga-sec h2 {{ display:flex; align-items:baseline; gap:10px; font-family:'Space Grotesk',sans-serif;
    font-size:20px; font-weight:700; border-bottom:1px solid var(--line2); padding-bottom:12px; margin:0; }}
  .liga-n {{ margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint);
    font-weight:400; letter-spacing:.5px; }}
  .ambiente {{ display:flex; flex-wrap:wrap; gap:10px; margin:16px 0 4px; }}
  .stat {{ flex:1; min-width:90px; padding:11px 12px; border:1px solid var(--line); border-radius:12px;
    background:var(--panel2); text-align:center; }}
  .stat-v {{ display:block; font-family:'IBM Plex Mono',monospace; font-size:18px; font-weight:600; color:var(--em); }}
  .stat-l {{ display:block; font-size:9.5px; color:var(--mut); text-transform:uppercase; letter-spacing:.6px; margin-top:3px; }}
  .subhead {{ font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:1.2px;
    text-transform:uppercase; color:var(--mut); margin:24px 0 0; }}
  .ranks {{ display:grid; grid-template-columns:1fr; gap:13px; margin-top:14px; }}
  @media(min-width:620px) {{ .ranks {{ grid-template-columns:1fr 1fr; }} }}
  @media(min-width:980px) {{ .ranks {{ grid-template-columns:1fr 1fr 1fr 1fr; }} }}
  .rcard {{ border:1px solid var(--line); border-radius:var(--r); padding:13px 14px;
    background:linear-gradient(180deg,var(--panel),var(--panel2)); }}
  .eyebrow {{ display:flex; flex-direction:column; gap:3px; margin-bottom:10px;
    font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:.6px; text-transform:uppercase; color:var(--bone); }}
  .eyebrow-x {{ color:var(--faint); font-size:9px; letter-spacing:.2px; text-transform:none; }}
  .rk {{ list-style:none; margin:0; padding:0; }}
  .rk li {{ display:flex; align-items:center; justify-content:space-between; gap:8px; padding:5px 0;
    border-top:1px solid var(--line2); font-size:12.5px; }}
  .rk li:first-child {{ border-top:none; }}
  .rk-n {{ color:#c2cdda; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .rk-v {{ font-family:'IBM Plex Mono',monospace; color:var(--em); font-variant-numeric:tabular-nums; }}
  details.padroes {{ margin-top:20px; border-top:1px solid var(--line2); }}
  details.padroes summary {{ cursor:pointer; font-family:'IBM Plex Mono',monospace; font-size:11px;
    letter-spacing:1px; text-transform:uppercase; color:var(--em); padding:14px 0 4px; list-style:none; }}
  details.padroes summary::-webkit-details-marker {{ display:none; }}
  .dna-grid {{ display:grid; grid-template-columns:1fr; gap:10px; margin-top:12px; }}
  @media(min-width:620px) {{ .dna-grid {{ grid-template-columns:1fr 1fr; }} }}
  @media(min-width:980px) {{ .dna-grid {{ grid-template-columns:1fr 1fr 1fr; }} }}
  .dna-card {{ border:1px solid var(--line); border-radius:12px; padding:11px 13px; background:var(--panel2); }}
  .dna-top {{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; }}
  .dna-top b {{ font-family:'Space Grotesk',sans-serif; font-size:14px; }}
  .dna-rec {{ font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--faint); white-space:nowrap; }}
  .dna-stats {{ font-size:11px; color:var(--mut); margin:6px 0 8px; line-height:1.5; }}
  .dna-flags {{ display:flex; flex-wrap:wrap; gap:5px; }}
  .dna-flags.dim {{ color:var(--faint); font-size:11px; }}
  .dna-flag {{ font-size:10.5px; background:rgba(52,226,160,.08); border:1px solid rgba(52,226,160,.22);
    color:#bfe9d6; padding:2px 8px; border-radius:999px; }}
  .vazio {{ text-align:center; color:var(--mut); margin-top:60px; }}
  .nota {{ max-width:760px; margin:18px auto 0; font-size:11.5px; line-height:1.55; color:var(--faint);
    border-left:2px solid var(--em); padding-left:13px; }}
  footer {{ text-align:center; color:var(--faint); font-size:10px; padding:24px 16px;
    font-family:'IBM Plex Mono',monospace; letter-spacing:.4px; }}
  footer b {{ color:var(--em); }}
</style>
</head>
<body>
  {_nav("tend")}
  <header>
    <h1>📊 Tendências</h1>
    <div class="sub">Leitura dos jogos já disputados — o scout do Cérebro, por liga</div>
    <div class="ts">xG · regressão à média · atualizado {data_geracao}</div>
    <div class="nota">Como ler: <b>xG</b> mostra a qualidade real das chances. Um time <b>azarado</b>
      (marca menos que o xG) tende a melhorar; um <b>sortudo</b> (marca mais) tende a regredir.
      É assim que se acha valor — e é o que o modelo já usa pesando 60% do xG.</div>
  </header>
  <main>{secoes}</main>
  <footer><b>Probabilidades FC</b> · tendências dos jogos já disputados · dados do 365scores</footer>
</body>
</html>"""
    destino = PASTA_SITE / "tendencias.html"
    destino.write_text(doc, encoding="utf-8")
    return destino


# ===================== ABA DICAS =====================

def _cor_dica(pct: int) -> str:
    if pct >= 72:
        return "#34e2a0"
    if pct >= 64:
        return "#84cc16"
    return "#f1b24a"


def card_dica(nome_m, nome_v, hora, liga_sel, dicas) -> str:
    linhas = ""
    for d in dicas:
        pct = round(d["p"] * 100)
        cor = _cor_dica(pct)
        conf = d.get("confianca", "provável")
        cls = "alta" if conf == "muito provável" else "media"
        why = html.escape(d["motivo"])
        if d.get("reforco"):
            why += f' · <b>{html.escape(d["reforco"])}</b>'
        linhas += (f'<div class="dica" style="border-left-color:{cor}">'
                   f'<div class="dica-head"><span class="dica-mkt">{html.escape(d["mercado"])}</span>'
                   f'<span class="dica-pct" style="color:{cor}">{pct}%</span></div>'
                   f'<div class="dica-conf {cls}">{conf}</div>'
                   f'<div class="dica-why">{why}</div></div>')
    return (f'<article class="dcard">'
            f'<div class="card-top"><span class="liga-tag">{liga_sel}</span>'
            f'<span class="hora">{html.escape(hora or "")}</span></div>'
            f'<div class="match"><span class="team">{html.escape(nome_m)}</span>'
            f'<span class="vs">vs</span><span class="team">{html.escape(nome_v)}</span></div>'
            f'<div class="dicas-list">{linhas}</div></article>')


def gerar_dicas_html(grupos_data, data_geracao: str) -> Path:
    """grupos_data = lista de (rotulo, subtitulo, [card_html])."""
    nomes = {"HOJE": "Hoje", "AMANHÃ": "Amanhã"}
    secoes = ""
    for rotulo, subtitulo, cards in grupos_data:
        if not cards:
            continue
        titulo = nomes.get(rotulo, rotulo)
        cls = "daymark hoje" if rotulo == "HOJE" else "daymark"
        secoes += f"""
      <section>
        <div class="{cls}"><span class="day">{titulo}</span>
          <span class="day-sub">{subtitulo}</span><span class="rule"></span>
          <span class="day-count">{len(cards)} jogo{'s' if len(cards) != 1 else ''}</span></div>
        <div class="grade">{''.join(cards)}</div>
      </section>"""
    if not secoes:
        secoes = '<p class="vazio">Sem dicas de alta confiança para hoje ou amanhã — jogos muito equilibrados.</p>'

    doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#090d13">
<title>Dicas · Probabilidades FC</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
  :root {{ --ink:#090d13; --panel:#0c121c; --panel2:#0a0f17; --line:#1a2433; --line2:#131b27;
    --bone:#e9ede9; --mut:#8593a3; --faint:#566678; --em:#34e2a0; --amber:#f1b24a; --r:14px; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; color:var(--bone); font-family:'Hanken Grotesk',system-ui,sans-serif;
    background: radial-gradient(900px 480px at 50% -260px,#11251c 0%,transparent 62%),
      radial-gradient(720px 420px at 100% -80px,#0e1a2a 0%,transparent 60%), var(--ink);
    background-attachment:fixed; -webkit-font-smoothing:antialiased; }}
  .nav {{ display:flex; flex-wrap:wrap; justify-content:center; gap:8px; padding:16px 16px 0; }}
  .nav a {{ font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.5px; text-decoration:none;
    color:var(--mut); padding:7px 16px; border:1px solid var(--line); border-radius:999px; }}
  .nav a.on {{ color:#04130d; background:var(--em); border-color:var(--em); font-weight:600; }}
  .nav a:hover {{ border-color:var(--em); color:var(--bone); }}
  header {{ text-align:center; padding:28px 18px 6px; }}
  header h1 {{ margin:0; font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:26px; }}
  header .sub {{ margin-top:8px; font-size:13px; color:var(--mut); }}
  header .ts {{ margin-top:6px; font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--faint);
    letter-spacing:1.4px; text-transform:uppercase; }}
  .nota {{ max-width:760px; margin:16px auto 0; font-size:11.5px; line-height:1.55; color:var(--faint);
    border-left:2px solid var(--em); padding-left:13px; }}
  main {{ max-width:1000px; margin:0 auto; padding:8px 16px 80px; }}
  .daymark {{ display:flex; align-items:baseline; gap:13px; position:sticky; top:0; z-index:6;
    padding:18px 2px 13px; background:var(--ink); box-shadow:0 10px 18px -6px var(--ink), 0 1px 0 0 var(--line2); }}
  .day {{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:21px; }}
  .daymark.hoje .day {{ color:var(--em); }}
  .day-sub {{ font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:var(--mut); }}
  .rule {{ flex:1; height:1px; background:linear-gradient(90deg,var(--line),transparent); }}
  .day-count {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint); }}
  .grade {{ display:grid; grid-template-columns:1fr; gap:14px; }}
  @media(min-width:760px) {{ .grade {{ grid-template-columns:1fr 1fr; }} }}
  .dcard {{ background:linear-gradient(180deg,var(--panel),var(--panel2)); border:1px solid var(--line);
    border-radius:var(--r); padding:15px; box-shadow:0 18px 40px -22px rgba(0,0,0,.8); }}
  .card-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:9px; }}
  .liga-tag {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:1.2px; text-transform:uppercase; color:var(--mut); }}
  .hora {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint); }}
  .match {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px; }}
  .team {{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16px; }}
  .vs {{ font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--faint); text-transform:uppercase; }}
  .dicas-list {{ display:flex; flex-direction:column; gap:9px; }}
  .dica {{ border:1px solid var(--line); border-left:3px solid var(--em); border-radius:10px; padding:9px 12px;
    background:var(--panel2); }}
  .dica-head {{ display:flex; justify-content:space-between; align-items:baseline; }}
  .dica-mkt {{ font-weight:600; font-size:14px; }}
  .dica-pct {{ font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:17px; font-variant-numeric:tabular-nums; }}
  .dica-conf {{ display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:9px; letter-spacing:1px;
    text-transform:uppercase; padding:2px 9px; border-radius:999px; margin-top:7px; }}
  .dica-conf.alta {{ color:#04130d; background:var(--em); font-weight:600; }}
  .dica-conf.media {{ color:var(--amber); border:1px solid rgba(241,178,74,.4); }}
  .dica-why {{ font-size:11.5px; color:var(--mut); margin-top:6px; line-height:1.45; }}
  .dica-why b {{ color:#c2cdda; font-weight:600; }}
  .vazio {{ text-align:center; color:var(--mut); margin-top:60px; }}
  footer {{ text-align:center; color:var(--faint); font-size:10px; padding:24px 16px;
    font-family:'IBM Plex Mono',monospace; letter-spacing:.4px; }}
  footer b {{ color:var(--em); }}
</style>
</head>
<body>
  {_nav("dicas")}
  <header>
    <h1>💡 Dicas</h1>
    <div class="sub">O que o Cérebro indica explorar — hoje e amanhã</div>
    <div class="ts">só mercados validados · atualizado {data_geracao}</div>
    <div class="nota">Modo <b>rígido</b>: só aparece o que é <b>muito provável</b> — o modelo precisa estar alto
      <b>e</b> o histórico dos dois times confirmar forte. Onde modelo e histórico discordam, não há dica
      (preferimos não indicar a indicar errado). Dias sem dica = jogos equilibrados. Aposte com responsabilidade.</div>
  </header>
  <main>{secoes}</main>
  <footer><b>Probabilidades FC</b> · dicas pelo modelo + padrões · sem odds</footer>
</body>
</html>"""
    destino = PASTA_SITE / "dicas.html"
    destino.write_text(doc, encoding="utf-8")
    return destino


# ===================== ABA HISTÓRICO =====================

def card_historico(row, liga_cfg=None) -> str:
    gm, gv = int(float(row["gm"])), int(float(row["gv"]))
    nm, nv = html.escape(row["mandante"]), html.escape(row["visitante"])
    cm = "win" if gm > gv else ("draw" if gm == gv else "")
    cv = "win" if gv > gm else ("draw" if gm == gv else "")

    def f(c):
        try:
            return float(row.get(c, "") or 0)
        except ValueError:
            return 0.0

    p = [f("p1"), f("px"), f("p2")]
    idx_pick, idx_real = p.index(max(p)), (0 if gm > gv else (1 if gm == gv else 2))
    pick_full = [f"Vitória {row['mandante']}", "Empate", f"Vitória {row['visitante']}"][idx_pick]
    tot = gm + gv
    over_call = f("po25") >= 0.5
    btts_call = f("pbtts") >= 0.5

    def chip(ok, txt, pct):
        ic = "✓" if ok else "✗"
        return f'<span class="hchip {"ok" if ok else "no"}">{ic} {html.escape(txt)} <i>{pct}%</i></span>'

    chips = (chip(idx_pick == idx_real, pick_full, round(max(p) * 100))
             + chip(over_call == (tot >= 3), "Over 2.5" if over_call else "Under 2.5",
                    round((f("po25") if over_call else 1 - f("po25")) * 100))
             + chip(btts_call == (gm >= 1 and gv >= 1), "Ambas" if btts_call else "Ambas não",
                    round((f("pbtts") if btts_call else 1 - f("pbtts")) * 100)))
    selo = f"{liga_cfg.get('emoji', '')} {html.escape(liga_cfg.get('nome', ''))}" if liga_cfg else ""
    return (f'<article class="hcard">'
            f'<div class="card-top"><span class="liga-tag">{selo}</span>'
            f'<span class="hora">{html.escape(row.get("hora", ""))}</span></div>'
            f'<div class="hplacar"><span class="pteam {cm}">{nm}</span>'
            f'<span class="pscore">{gm}<i>–</i>{gv}</span>'
            f'<span class="pteam {cv}">{nv}</span></div>'
            f'<div class="hchips">{chips}</div></article>')


def gerar_historico_html(grupos_data, data_geracao: str, resumo=None) -> Path:
    nomes = {"HOJE": "Hoje", "ONTEM": "Ontem"}
    secoes = ""
    for rotulo, subtitulo, cards in grupos_data:
        if not cards:
            continue
        titulo = nomes.get(rotulo, rotulo)
        secoes += f"""
      <section>
        <div class="daymark"><span class="day">{titulo}</span>
          <span class="day-sub">{subtitulo}</span><span class="rule"></span>
          <span class="day-count">{len(cards)} jogo{'s' if len(cards) != 1 else ''}</span></div>
        <div class="grade">{''.join(cards)}</div>
      </section>"""
    if not secoes:
        secoes = ('<p class="vazio">Ainda sem jogos conferidos. Assim que as partidas mostradas '
                  'terminarem, os resultados aparecem aqui — automaticamente.</p>')

    resumo_html = ""
    if resumo and resumo.get("n"):
        resumo_html = (f'<div class="resumo">Em <b>{resumo["n"]}</b> jogos conferidos, o modelo acertou: '
                       f'<b>resultado</b> {resumo["res"]:.0%} · <b>over/under</b> {resumo["over"]:.0%} · '
                       f'<b>ambas marcam</b> {resumo["btts"]:.0%}</div>')

    doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#090d13">
<title>Histórico · Probabilidades FC</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
  :root {{ --ink:#090d13; --panel:#0c121c; --panel2:#0a0f17; --line:#1a2433; --line2:#131b27;
    --bone:#e9ede9; --mut:#8593a3; --faint:#566678; --em:#34e2a0; --amber:#f1b24a; --red:#ef6a6a; --r:14px; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; color:var(--bone); font-family:'Hanken Grotesk',system-ui,sans-serif;
    background: radial-gradient(900px 480px at 50% -260px,#11251c 0%,transparent 62%),
      radial-gradient(720px 420px at 100% -80px,#0e1a2a 0%,transparent 60%), var(--ink);
    background-attachment:fixed; -webkit-font-smoothing:antialiased; }}
  .nav {{ display:flex; flex-wrap:wrap; justify-content:center; gap:8px; padding:16px 16px 0; }}
  .nav a {{ font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.5px; text-decoration:none;
    color:var(--mut); padding:7px 16px; border:1px solid var(--line); border-radius:999px; }}
  .nav a.on {{ color:#04130d; background:var(--em); border-color:var(--em); font-weight:600; }}
  .nav a:hover {{ border-color:var(--em); color:var(--bone); }}
  header {{ text-align:center; padding:28px 18px 6px; }}
  header h1 {{ margin:0; font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:26px; }}
  header .sub {{ margin-top:8px; font-size:13px; color:var(--mut); }}
  header .ts {{ margin-top:6px; font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--faint);
    letter-spacing:1.4px; text-transform:uppercase; }}
  .resumo {{ max-width:760px; margin:16px auto 0; padding:12px 16px; text-align:center; font-size:12.5px;
    color:var(--mut); border:1px solid var(--line); border-radius:12px; background:var(--panel2); }}
  .resumo b {{ color:var(--em); }}
  main {{ max-width:1000px; margin:0 auto; padding:8px 16px 80px; }}
  .daymark {{ display:flex; align-items:baseline; gap:13px; position:sticky; top:0; z-index:6;
    padding:18px 2px 13px; background:var(--ink); box-shadow:0 10px 18px -6px var(--ink), 0 1px 0 0 var(--line2); }}
  .day {{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:21px; color:var(--bone); }}
  .day-sub {{ font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:var(--mut); }}
  .rule {{ flex:1; height:1px; background:linear-gradient(90deg,var(--line),transparent); }}
  .day-count {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint); }}
  .grade {{ display:grid; grid-template-columns:1fr; gap:14px; }}
  @media(min-width:760px) {{ .grade {{ grid-template-columns:1fr 1fr; }} }}
  .hcard {{ background:linear-gradient(180deg,var(--panel),var(--panel2)); border:1px solid var(--line);
    border-radius:var(--r); padding:15px; box-shadow:0 18px 40px -22px rgba(0,0,0,.8); }}
  .card-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:11px; }}
  .liga-tag {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:1.2px; text-transform:uppercase; color:var(--mut); }}
  .hora {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint); }}
  .hplacar {{ display:flex; align-items:center; gap:10px; margin-bottom:13px; }}
  .pteam {{ flex:1; font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:15.5px; color:var(--mut); }}
  .pteam:last-child {{ text-align:right; }}
  .pteam.win {{ color:var(--em); }}
  .pteam.draw {{ color:var(--bone); }}
  .pscore {{ font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:22px; color:var(--bone);
    font-variant-numeric:tabular-nums; }}
  .pscore i {{ color:var(--faint); font-style:normal; margin:0 3px; }}
  .hchips {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .hchip {{ font-family:'IBM Plex Mono',monospace; font-size:10.5px; padding:3px 9px; border-radius:999px;
    border:1px solid var(--line); color:var(--mut); }}
  .hchip i {{ font-style:normal; color:var(--faint); }}
  .hchip.ok {{ color:var(--em); border-color:rgba(52,226,160,.35); background:rgba(52,226,160,.07); }}
  .hchip.no {{ color:var(--red); border-color:rgba(239,106,106,.3); }}
  .hchip.ok i {{ color:#9fd8c2; }}
  .vazio {{ text-align:center; color:var(--mut); margin-top:60px; line-height:1.6; max-width:520px; margin-left:auto; margin-right:auto; }}
  footer {{ text-align:center; color:var(--faint); font-size:10px; padding:24px 16px;
    font-family:'IBM Plex Mono',monospace; letter-spacing:.4px; }}
  footer b {{ color:var(--em); }}
</style>
</head>
<body>
  {_nav("hist")}
  <header>
    <h1>📅 Histórico</h1>
    <div class="sub">Resultado das partidas que apareceram — e se o modelo acertou</div>
    <div class="ts">✓ acertou · ✗ errou · atualizado {data_geracao}</div>
    {resumo_html}
  </header>
  <main>{secoes}</main>
  <footer><b>Probabilidades FC</b> · histórico real · sem odds</footer>
</body>
</html>"""
    destino = PASTA_SITE / "historico.html"
    destino.write_text(doc, encoding="utf-8")
    return destino
