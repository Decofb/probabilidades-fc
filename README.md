# ⚽ Probabilidades FC

Bot/site que calcula **probabilidades em %** (nunca odds) para jogos de futebol,
a partir das estatísticas dos times. Mercados:

- 🏆 **Resultado (1X2)** — vitória mandante / empate / visitante
- ⚽ **Over/Under** (1.5 e 2.5 gols) + **Ambas Marcam (BTTS)**
- ⚖️ **Handicap Asiático**
- ⛳ **Escanteios** (over 7.5 a 11.5)

As % saem de um **modelo Poisson** alimentado por: gols feitos/sofridos, xG/xGA e
escanteios feitos/cedidos dos últimos jogos. **Sem odds. Sem casa de apostas.**

---

## Como usar (todo dia)

```
python atualizar.py            # tenta buscar do FBref e gera o site
python atualizar.py --offline  # usa só as planilhas (CSV), não tenta a internet
```

Depois abra **`site/index.html`** no navegador. (Dá pra publicar de graça — veja abaixo.)

---

## De onde vêm os dados

| Dado | Fonte | Arquivo |
|------|-------|---------|
| Estatísticas dos times (gols, xG, escanteios) | FBref | `dados/<liga>_times.csv` |
| Tabela de jogos | FIFA.com / ge.globo | `dados/<liga>_jogos.csv` |

> ⚠️ **Importante sobre o FBref:** o site tem proteção Cloudflare e bloqueia robôs.
> A busca automática pode falhar. Por isso o sistema **sempre tem um plano B**: os
> arquivos `.csv` em `dados/`. Você (ou um agente agendado) preenche/cola os números
> e o site funciona 100% offline. Os CSVs são editáveis no Excel.

### Planilha de times (`dados/<liga>_times.csv`)
```
time,jogos,gols_feitos,gols_sofridos,xg,xga,esc_feitos,esc_sofridos
Holanda,6,2.3,0.7,2.10,0.80,6.5,3.2
```
Todas as colunas são **médias por jogo**. `xg/xga/esc_*` são opcionais (deixe vazio se não tiver).

### Planilha de jogos (`dados/<liga>_jogos.csv`)
```
data,hora,mandante,visitante,rodada
2026-06-25,16:00,Tunisia,Holanda,Grupo - 3ª rodada
```

---

## Estrutura

```
probabilidades-fc/
  motor/
    poisson.py     # matemática dos mercados (1X2, O/U, BTTS, handicap, escanteios)
    forca.py       # transforma estatística em "gols esperados" (lambda)
  dados/
    fonte.py       # carrega stats (FBref -> CSV)
    jogos.py       # carrega tabela de jogos (CSV)
    *.csv          # dados das ligas
  site_gerador.py  # monta o site HTML
  atualizar.py     # >>> o comando que você roda <<<
  site/index.html  # o site gerado
```

## Publicar o site (acompanhar no celular)
O `site/index.html` é estático. É só subir a pasta `site/` em **Netlify Drop**
(netlify.com/drop) ou **Vercel** e você tem um link pra abrir no celular todo dia.

---

⚠️ **As porcentagens são estimativas estatísticas, não garantias.** Futebol tem zebra.
Use como apoio à decisão, com responsabilidade.
