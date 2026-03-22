@echo off
setlocal
cd /d "%~dp0"

set "STREAMLIT_ADDR=0.0.0.0"
set "STREAMLIT_PORT=8501"

python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
  echo Installing streamlit...
  python -m pip install -U streamlit
)

python -c "import opendataloader_pdf" >nul 2>nul
if errorlevel 1 (
  echo Installing opendataloader-pdf...
  python -m pip install -U opendataloader-pdf
)

python -c "import fastapi,uvicorn,docling" >nul 2>nul
if errorlevel 1 (
  echo Installing OCR dependencies...
  python -m pip install -U "opendataloader-pdf[hybrid]"
)

python -c "import pypdf" >nul 2>nul
if errorlevel 1 (
  echo Installing pypdf...
  python -m pip install -U pypdf
)

echo.
echo Starting Streamlit server for LAN access...
echo Listening on %STREAMLIT_ADDR%:%STREAMLIT_PORT%
echo Access URLs from other PCs:
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -notlike '169.254*' -and $_.IPAddress -ne '127.0.0.1' } ^| Select-Object -ExpandProperty IPAddress"') do (
  echo   http://%%I:%STREAMLIT_PORT%
)

netsh advfirewall firewall show rule name="OpenDataLoader Streamlit %STREAMLIT_PORT%" >nul 2>&1
if errorlevel 1 (
  netsh advfirewall firewall add rule name="OpenDataLoader Streamlit %STREAMLIT_PORT%" dir=in action=allow protocol=TCP localport=%STREAMLIT_PORT% >nul 2>&1
  if errorlevel 1 (
    echo [WARN] Could not add Windows Firewall rule automatically.
    echo [WARN] Run run_ui.bat once as Administrator, or allow TCP %STREAMLIT_PORT% manually.
  ) else (
    echo Firewall rule added for TCP %STREAMLIT_PORT%.
  )
)

python -m streamlit run app_streamlit.py --server.fileWatcherType none --server.address %STREAMLIT_ADDR% --server.port %STREAMLIT_PORT%
