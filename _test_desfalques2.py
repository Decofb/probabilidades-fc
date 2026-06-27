"""Valida parser com artigo GE Cartola real (Rodada 18)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from dados.desfalques import parsear_desfalques, desfalques_do_jogo

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36', 'Accept-Language': 'pt-BR,pt;q=0.9'}
URL = ('https://ge.globo.com/cartola/noticia/2026/05/30/'
       'cartola-2026-veja-suspensos-lesionados-e-escalacoes-provaveis-'
       'da-rodada-18-do-brasileirao.ghtml')

r = requests.get(URL, headers=HEADERS, timeout=20)
print(f"HTTP {r.status_code}  ({len(r.text)} chars)")

dados = parsear_desfalques(r.text)
print(f"\nTimes parseados: {len(dados)}")

for nome, d in list(dados.items()):
    sus = ", ".join(d["suspensos"])
    les = ", ".join(d["lesionados"])
    if sus or les:
        print(f"  {d['time_original']:25s}  Susp: {sus or '-'}  Les: {les or '-'}")

print("\n--- Teste desfalques_do_jogo ---")
dj = desfalques_do_jogo("Athletico-PR", "Atletico Mineiro", dados)
print("Mandante suspensos:", dj["mandante"]["suspensos"])
print("Mandante lesionados:", dj["mandante"]["lesionados"])
print("Visitante suspensos:", dj["visitante"]["suspensos"])
print("Visitante lesionados:", dj["visitante"]["lesionados"])
print("tem_desfalque:", dj["tem_desfalque"])
