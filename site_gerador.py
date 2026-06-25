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


def card_jogo(j: Jogo, m: ResultadoMercados, ha: dict | None, linha_ha: float,
              liga_cfg: dict | None = None) -> str:
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

    # handicap
    if ha:
        sinal = "+" if linha_ha >= 0 else ""
        outra = f"{'-' if linha_ha >= 0 else '+'}{abs(linha_ha)}"
        hc = (_mercado(f"{nome_m} {sinal}{linha_ha}", round(ha['mandante'] * 100)) +
              _mercado(f"{nome_v} {outra}", round(ha['visitante'] * 100)))
        blocos += _bloco("Handicap asiático", "", hc)

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
               dados_backup: bool = False) -> Path:
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
  footer {{ text-align:center; color:var(--faint); font-size:10.5px; padding:30px 16px;
    font-family:'IBM Plex Mono',monospace; letter-spacing:.4px; }}
  footer b {{ color:var(--em); font-weight:500; }}

  @keyframes grow {{ from {{ width:0; }} to {{ width:var(--w); }} }}
  @media(prefers-reduced-motion:reduce) {{ .seg, .m-track .fill {{ animation:none; }} }}
</style>
</head>
<body>
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
  <footer><b>Probabilidades FC</b> · modelo Poisson + Dixon-Coles · dados do 365scores</footer>
</body>
</html>"""

    destino = PASTA_SITE / "index.html"
    destino.write_text(html_doc, encoding="utf-8")
    return destino
