@echo off
REM Cambia al directorio donde se encuentra este script .bat
cd /d "%~dp0"

REM --- 1. Lee las variables del archivo .env ---
IF NOT EXIST ".env" (
    echo ERROR: No se encontro el archivo .env.
    goto :end
)
echo Leyendo variables de entorno desde .env...
for /f "tokens=1,2 delims==" %%A in (.env) do (
    set "%%A=%%B"
)
IF "%NGROK_URL%"=="" (
    echo ERROR: La variable NGROK_URL no se encontro en el archivo .env o esta vacia.
    goto :end
)
echo Variables cargadas.

REM --- 2. Inicia ngrok en una nueva ventana ---
echo Iniciando ngrok...
start "ngrok Tunnel" cmd /c ".\ngrok.exe http --url=%NGROK_URL% %PORT%"

:end