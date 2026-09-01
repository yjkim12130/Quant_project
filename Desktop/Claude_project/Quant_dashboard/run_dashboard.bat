@echo off
echo ========================================
echo   YJ-Quant Dashboard 시작 중...
echo ========================================
echo.

cd /d "%~dp0"

REM PC에서 접속: http://localhost:8501
REM 모바일에서 접속: http://192.168.219.117:8501 (같은 와이파이)

python -m streamlit run streamlit_app.py ^
  --server.address 0.0.0.0 ^
  --server.port 8501 ^
  --server.headless false ^
  --browser.gatherUsageStats false

pause
