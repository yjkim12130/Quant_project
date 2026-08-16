@echo off
REM 자문역 인사이트 통합 분석 (P3, 독립 앱) — v9.3과 별개
REM DART 재무 연동을 원하면 아래 줄의 주석을 풀고 키를 넣으세요.
REM set DART_API_KEY=발급받은_DART_인증키
cd /d "%~dp0"
python -m streamlit run advisor_app.py
