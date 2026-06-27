import sys; sys.stdout.reconfigure(encoding='utf-8')
import requests, re
headers = {'User-Agent': 'Mozilla/5.0 Chrome/124', 'Accept-Language': 'pt-BR,pt;q=0.9'}
for slug in ['serie-b', 'serie-b-2026']:
    r = requests.get(f'https://www.flashscore.com.br/futebol/brasil/{slug}/resultados/', headers=headers, timeout=10)
    blocos = r.text.split('~AA')
    finished = sum(1 for b in blocos if 'AB÷3' in b)
    print(f'{slug}: {len(blocos)-1} blocos, {finished} finalizados')
    for b in blocos[1:]:
        if 'AB÷3' in b:
            af = re.search(r'AF÷([^¬]+)', b)
            ae = re.search(r'AE÷([^¬]+)', b)
            er = re.search(r'ER÷([^¬]+)', b)
            if af and ae:
                print(f'  ex: {af.group(1)} vs {ae.group(1)} [{er.group(1) if er else "?"}]')
            break
