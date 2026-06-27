"""Testa onde estão as estatísticas (xG, escanteios) na página de jogo."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import re, requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}

url = "https://www.flashscore.com.br/jogo/futebol/fluminense-EV9L3kU4/cruzeiro-0SwtclaU/"
r = requests.get(url, headers=HEADERS, timeout=20)
page = r.text

# Busca xG em qualquer posição
idx_xg = [m.start() for m in re.finditer(r'[xX][gG]', page)]
print(f"'xG' encontrado em {len(idx_xg)} posições")
for idx in idx_xg[:5]:
    print(f"  pos {idx}: ...{repr(page[max(0,idx-50):idx+80])}...")

# Testa também o endpoint de stats da API ninja do Flashscore
match_id = '0Y57Mqm1'
ninja_url = f"https://2.flashscore.ninja/x/feed/match-statistic-{match_id}"
print(f"\nTestando ninja API: {ninja_url}")
r2 = requests.get(ninja_url, headers={**HEADERS, 'Referer': 'https://www.flashscore.com.br/'}, timeout=15)
print(f"  Status: {r2.status_code}, tamanho: {len(r2.text)}")
if r2.status_code == 200:
    print(f"  Primeiros 500 chars: {repr(r2.text[:500])}")

# Testa endpoint alternativo
api_url = f"https://www.flashscore.com.br/x/feed/df_st_{match_id}"
print(f"\nTestando df_st API: {api_url}")
r3 = requests.get(api_url, headers={**HEADERS, 'X-Fsign': 'SW9D1eZo'}, timeout=15)
print(f"  Status: {r3.status_code}, tamanho: {len(r3.text)}")
if r3.status_code == 200:
    print(f"  Primeiros 500 chars: {repr(r3.text[:500])}")
