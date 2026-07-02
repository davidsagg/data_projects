@echo off
REM Script de Setup - OKR Portfolio Dashboard
REM Execute este script para configurar o projeto pela primeira vez

echo.
echo ========================================
echo  OKR Portfolio Dashboard - Setup
echo ========================================
echo.

REM Verificar se Node.js está instalado
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Node.js nao encontrado!
    echo.
    echo Por favor, instale Node.js 18+ de: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo [OK] Node.js encontrado
node -v
echo [OK] npm encontrado
call npm -v
echo.

REM Verificar se está na pasta correta
if not exist "package.json" (
    echo [ERRO] package.json nao encontrado!
    echo Execute este script dentro da pasta okr-portfolio-dashboard
    echo.
    pause
    exit /b 1
)

echo Instalando dependencias...
echo.
call npm install

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo  Setup concluido com sucesso!
    echo ========================================
    echo.
    echo Proximos passos:
    echo   1. Execute: npm run dev
    echo   2. Abra: http://localhost:5173
    echo.
    echo Outros comandos uteis:
    echo   npm run build   - Gerar build de producao
    echo   npm run preview - Visualizar build localmente
    echo.
) else (
    echo.
    echo [ERRO] Falha ao instalar dependencias
    echo.
    pause
    exit /b 1
)

pause
