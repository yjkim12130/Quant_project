import os

import streamlit as st

APP_PASSWORD_FILE = ".app_password"


def get_app_password(env=None, secrets=None, path=APP_PASSWORD_FILE):
    """배포 환경(Streamlit Cloud)의 Secrets, 로컬 환경변수, 로컬 파일 순으로 확인.
    셋 다 없으면 None을 반환하고, 이 경우 게이트는 비활성화된다(로컬 개발용)."""
    if secrets:
        value = secrets.get("APP_PASSWORD")
        if value:
            return str(value).strip()
    env = os.environ if env is None else env
    value = env.get("APP_PASSWORD")
    if value:
        return value.strip()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return None


def require_password():
    try:
        secrets = dict(st.secrets)
    except Exception:
        secrets = None
    required = get_app_password(secrets=secrets)
    if not required:
        return
    if st.session_state.get("_authed"):
        return
    st.title("🔒 접근 확인")
    pw = st.text_input("비밀번호", type="password", key="_pw_input")
    if st.button("입장", type="primary"):
        if pw == required:
            st.session_state["_authed"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()
