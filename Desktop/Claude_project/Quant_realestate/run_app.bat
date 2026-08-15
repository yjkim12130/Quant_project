@echo off
rem YJ-RealEstate 실행: Streamlit(8502) + 외부 공유 터널
rem 터널 창에 표시되는 https://xxx.trycloudflare.com 주소가 외부 접속용 (재시작마다 변경됨)
cd /d "%~dp0"
start "YJ-RealEstate 앱" cmd /k streamlit run app.py --server.headless true
timeout /t 5 /nobreak >nul
start "외부 공유 터널" cmd /k "%USERPROFILE%\.claude\tools\cloudflared.exe" tunnel --url http://localhost:8502
echo.
echo  로컬:   http://localhost:8502
echo  모바일(Tailscale): http://100.107.38.73:8502
echo  외부공유: "외부 공유 터널" 창의 trycloudflare.com 주소 확인
pause
