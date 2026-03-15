@echo off
setlocal EnableExtensions

set "ROOT=C:\DesignKP"
set "BACKEND_DIR=%ROOT%\backend"
set "UI_DIR=%ROOT%\2d\ui"
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"

echo ==========================================
echo DesignKP Launcher
echo Root: %ROOT%
echo ==========================================

if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python runtime not found:
  echo %PYTHON_EXE%
  goto :fail
)

if not exist "%NPM_CMD%" (
  echo [ERROR] npm not found:
  echo %NPM_CMD%
  goto :fail
)

if not exist "%BACKEND_DIR%" (
  echo [ERROR] Backend folder not found:
  echo %BACKEND_DIR%
  goto :fail
)

if not exist "%UI_DIR%" (
  echo [ERROR] UI folder not found:
  echo %UI_DIR%
  goto :fail
)

if not exist "%UI_DIR%\node_modules" (
  echo [ERROR] UI dependencies not found. Run this once:
  echo cd /d "%UI_DIR%"
  echo "%NPM_CMD%" install
  goto :fail
)

echo [INFO] Starting backend...
start "DesignKP Backend" cmd /k cd /d "%BACKEND_DIR%" ^& "%PYTHON_EXE%" -m uvicorn designkp_backend.main:app --host 127.0.0.1 --port 8000

echo [INFO] Starting frontend...
start "DesignKP Frontend" cmd /k cd /d "%UI_DIR%" ^& call "%NPM_CMD%" run dev -- --port 5174

echo [INFO] Waiting for frontend...
timeout /t 6 /nobreak >nul
start "" "http://127.0.0.1:5174"

echo [OK] Backend and frontend start commands were sent.
echo If a window closes, read the error in that window.
goto :eof

:fail
echo.
echo [FAILED] DesignKP did not start.
pause
exit /b 1
