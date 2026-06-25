@echo off
REM === Probabilidades FC - atualizacao diaria automatica ===
REM Busca dados do 365scores, gera o site e publica no GitHub Pages.
cd /d "%~dp0"
if not exist logs mkdir logs

echo ========================================== >> logs\cron.log
echo Rodada em %date% %time% >> logs\cron.log

REM 1) Atualiza dados e gera o site
"%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" atualizar.py >> logs\cron.log 2>&1

REM 2) Publica (so commita se houver mudanca)
git add -A >> logs\cron.log 2>&1
git diff --cached --quiet || git commit -m "Atualizacao automatica" >> logs\cron.log 2>&1
git push >> logs\cron.log 2>&1

echo Fim em %date% %time% >> logs\cron.log
