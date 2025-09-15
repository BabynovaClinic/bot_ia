@echo off
REM Cambia al directorio donde se encuentra este script .bat
cd /d "%~dp0"

REM Define el nombre del entorno virtual
set VENV_NAME=.venv
set VENV_PATH=%VENV_NAME%\Scripts\activate.bat

REM --- 1. Busca el entorno virtual y lo crea si no existe ---
IF EXIST "%VENV_PATH%" (
    echo Entorno virtual "%VENV_NAME%" encontrado.
) ELSE (
    echo Entorno virtual "%VENV_NAME%" no encontrado. Creándolo...
    python -m venv %VENV_NAME%
    IF NOT EXIST "%VENV_PATH%" (
        echo ERROR: No se pudo crear el entorno virtual "%VENV_NAME%".
        echo Asegúrese de que Python está en su PATH y que tiene permisos.
        goto :end
    )
    echo Entorno virtual "%VENV_NAME%" creado exitosamente.
)

REM --- 2. Activa el entorno virtual ---
call "%VENV_PATH%"
IF ERRORLEVEL 1 (
    echo ERROR: Fallo al activar el entorno virtual "%VENV_NAME%".
    goto :end
)
echo Entorno virtual activado.

REM --- 3. Instala los requerimientos si el archivo existe ---
IF EXIST "requirements.txt" (
    echo Instalando/Verificando dependencias desde requirements.txt...
    pip install -r requirements.txt >NUL 2>NUL
    IF ERRORLEVEL 1 (
        echo ERROR: Fallo al instalar dependencias desde requirements.txt.
        goto :end
    )
    echo Dependencias instaladas/verificadas.
) ELSE (
    echo Advertencia: No se encontró el archivo requirements.txt. Saltando instalación de dependencias.
)

REM --- 4. Lee las variables del archivo .env ---
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

REM --- 5. Inicia ngrok en una nueva ventana ---
echo Iniciando ngrok...
start "ngrok Tunnel" cmd /c ".\ngrok.exe http --url=%NGROK_URL% %PORT%"

REM --- 6. Ejecuta el script principal ---
echo Iniciando MaIA...
python app.py

:end

REM --- 7. Agrega una pausa al final ---
pause