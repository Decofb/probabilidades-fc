"""Analisa estrutura HTML do artigo GE Cartola."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests, re
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}
URL = ('https://ge.globo.com/cartola/noticia/2026/05/30/cartola-2026-veja-suspensos-lesionados-'
       'e-escalacoes-provaveis-da-rodada-18-do-brasileirao.ghtml')

r = requests.get(URL, headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, 'html.parser')

# Tentar extrair conteúdo de texto do artigo
# GE Globo: conteúdo do artigo geralmente em <div class="content-text"> ou similares
content_divs = (
    soup.find_all('div', class_=re.compile(r'content|article|body|texto', re.I))
)
print(f'{len(content_divs)} divs de conteúdo encontrados')

# Pegar o maior bloco de texto
maior = max(content_divs, key=lambda d: len(d.get_text()), default=None)
if maior:
    texto = maior.get_text('\n', strip=True)
    print(f'\nMaior bloco: {len(texto)} chars')
    print('\n=== PRIMEIROS 3000 chars ===')
    print(texto[:3000])

# Também verificar tags específicas do GE
for tag in ['h2', 'h3', 'strong', 'b']:
    items = soup.find_all(tag)[:5]
    if items:
        print(f'\n{tag} tags: {[i.get_text(strip=True)[:60] for i in items]}')
