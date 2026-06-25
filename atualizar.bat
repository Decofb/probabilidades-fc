@echo off
REM === Probabilidades FC - atualizacao diaria automatica ===
REM Busca dados do 365scores, gera o site e publica no GitHub Pages.
cd /d "%~dp0"
if not exist logs mkdir logs

echo ========================================== >> logs\cron.log
echo Rodada em %date% %time% >> logs\cron.log

REM 1) Atualiza dados e gera o site. Se o python falhar (exit != 0), NAO publica.
"%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" atualizar.py >> logs\cron.log 2>&1
if errorlevel 1 (
  echo [ERRO] coleta/geracao falhou exit=%errorlevel% - publicacao ABORTADA >> logs\cron.log
  echo Fim em %date% %time% >> logs\cron.log
  exit /b 1
)

REM 2) Publica so se houver mudanca; aborta com aviso se o push falhar.
git add -A >> logs\cron.log 2>&1
git diff --cached --quiet && (
  echo [OK] sem mudancas para publicar >> logs\cron.log
) || (
  git commit -m "Atualizacao automatica" >> logs\cron.log 2>&1
  git push >> logs\cron.log 2>&1
  if errorlevel 1 (
    echo [ERRO] git push falhou - site NAO atualizado no ar >> logs\cron.log
    echo Fim em %date% %time% >> logs\cron.log
    exit /b 1
  )
  echo [OK] publicado >> logs\cron.log
)

echo Fim em %date% %time% >> logs\cron.log
