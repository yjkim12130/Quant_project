@echo off
title 윤진 Studio
cd /d "%~dp0"

echo.
echo   윤진 Studio 를 켜는 중입니다. 20초쯤 걸려요.
echo.
echo   잠시 뒤 아래에 주소가 나옵니다.
echo     Local URL   - 이 PC에서 쓸 주소
echo     Network URL - 폰이나 노트북에서 쓸 주소 (같은 집 Wi-Fi)
echo.
echo   External URL 은 무시하세요. 집 밖에서는 안 됩니다.
echo   이 검은 창을 닫으면 앱도 꺼집니다.
echo.

python -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false

echo.
echo   앱이 종료되었습니다. 아무 키나 누르면 창이 닫힙니다.
pause > nul
