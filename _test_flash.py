"""Testa estrutura dos dados do Flashscore para um jogo específico."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}

r = requests.get('https://www.flashscore.com.br/futebol/brasil/brasileirao-betano/resultados/',
                  headers=HEADERS, timeout=20)
html = r.text

# Parse all blocks
blocks = html.split('~AA÷')
print(f'{len(blocks)-1} blocos encontrados\n')

def parse_block(raw):
    """Parseia bloco ¬ em dict."""
    parts = re.split(r'¬([A-Z]{2})÷', raw)
    d = {}
    if parts:
        d['AA'] = parts[0].split('¬')[0]  # match_id is before first ¬
    for i in range(1, len(parts)-1, 2):
        d[parts[i]] = parts[i+1].split('¬')[0] if '¬' in parts[i+1] else parts[i+1]
    return d

# Show first 3 finished matches
count = 0
sample_match = None
for blk in blocks[1:]:
    d = parse_block(blk)
    if d.get('AB') == '3':  # finished
        home = d.get('AF', '?')
        away = d.get('AE', '?')
        gh = d.get('AH', '?')
        ga = d.get('AG', '?')
        ts = d.get('AD', '0')
        round_ = d.get('ER', '?')
        home_slug = d.get('WV', '')
        away_slug = d.get('WU', '')
        home_id = d.get('PY', '')
        away_id = d.get('PX', '')
        print(f"[{round_}] {home} {gh}-{ga} {away}")
        print(f"  match_id={d.get('AA')} ts={ts}")
        print(f"  home_slug={home_slug} home_id={home_id}")
        print(f"  away_slug={away_slug} away_id={away_id}")
        if sample_match is None and home_slug and home_id and away_slug and away_id:
            sample_match = d
        count += 1
        if count >= 3:
            break

# Test per-match stats URL
if sample_match:
    home_slug = sample_match.get('WV', '')
    home_id = sample_match.get('PY', '')
    away_slug = sample_match.get('WU', '')
    away_id = sample_match.get('PX', '')
    url = f"https://www.flashscore.com.br/jogo/futebol/{home_slug}-{home_id}/{away_slug}-{away_id}/"
    print(f"\nTestando URL de estatísticas:")
    print(f"  {url}")
    r2 = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  Status: {r2.status_code}, tamanho: {len(r2.text)} bytes")
    page = r2.text
    # Look for xG pattern
    xg_patterns = re.findall(r'xG[^0-9]*(\d+\.\d+)', page[:5000])
    print(f"  xG patterns (primeiros 5000 chars): {xg_patterns}")
    # Look in script tags
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', page, re.DOTALL)
    print(f"  {len(scripts)} script tags")
    for s in scripts[:5]:
        if 'xG' in s or 'statistic' in s.lower():
            print(f"  Script com xG/statistic (primeiros 200 chars): {s[:200]}")
            break
