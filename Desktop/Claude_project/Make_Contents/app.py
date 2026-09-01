"""윤진 Studio — 레시피 콘텐츠 생성기."""

import json
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from yunjin_studio.context import ROOT, load_profile
from yunjin_studio.formatter import render_blog, render_instagram, render_shooting_guide
from yunjin_studio.generator import generate_publish, generate_shooting
from yunjin_studio.recipe import list_recipes, load_recipe
from yunjin_studio.schema import validate_publish_pack, validate_shooting_guide

load_dotenv(ROOT / ".env")

st.set_page_config(page_title="윤진 Studio", page_icon="🍳", layout="wide")
st.title("🍳 윤진 Studio")
st.caption(
    "레시피 텍스트 하나로 촬영 가이드 · 인스타 · 블로그를 만듭니다. "
    "생성 버튼을 누르면 **6분쯤** 걸려요 — 눌러두고 다른 일 하셔도 됩니다."
)

profile, warnings = load_profile()
for warning in warnings:
    st.warning(warning)

names = list_recipes()
if not names:
    st.error("Recipe 폴더에 .txt 파일이 없습니다.")
    st.stop()

col_left, col_right = st.columns([2, 1])
with col_left:
    name = st.selectbox("레시피", names)
with col_right:
    duration = st.selectbox("목표 러닝타임(초)", [30, 60, 90], index=1)
episode = st.text_input("비하인드 에피소드 (선택)", "")

if st.button("생성", type="primary"):
    recipe = load_recipe(name, episode=episode)
    out_dir = ROOT / "output" / f"{date.today():%Y-%m-%d}_{name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 호출①의 결과를 먼저 디스크에 남긴다. 호출②가 실패해도 살아남게 하기 위함(스펙 §12).
    with st.spinner("① 촬영 가이드를 만드는 중… 3분쯤 걸려요. 창을 닫지 마세요."):
        shooting = generate_shooting(profile, recipe, duration_sec=duration)
    (out_dir / "_raw_shooting.json").write_text(
        json.dumps(shooting, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with st.spinner("② 인스타·블로그를 만드는 중… 3분쯤 더 걸려요."):
        publish = generate_publish(profile, shooting.get("recipe_card") or {})
    (out_dir / "_raw_publish.json").write_text(
        json.dumps(publish, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    measure_note = (shooting.get("recipe_card") or {}).get("measure_note", "")
    errors = validate_shooting_guide(shooting) + validate_publish_pack(publish, measure_note)
    if errors:
        st.warning("검증 경고 " + str(len(errors)) + "건")
        for error in errors:
            st.write("- " + error)

    st.session_state["result"] = (str(out_dir), shooting, publish)

if "result" in st.session_state:
    out_dir_str, shooting, publish = st.session_state["result"]
    out_dir = Path(out_dir_str)

    card_md = json.dumps(shooting.get("recipe_card") or {}, ensure_ascii=False, indent=2)
    guide_md = render_shooting_guide(shooting)
    insta_md = render_instagram(publish)
    blog_md = render_blog(publish)

    (out_dir / "00_recipe_card.json").write_text(card_md, encoding="utf-8")
    (out_dir / "01_촬영가이드.md").write_text(guide_md, encoding="utf-8")
    (out_dir / "02_인스타.md").write_text(insta_md, encoding="utf-8")
    (out_dir / "03_블로그.md").write_text(blog_md, encoding="utf-8")

    st.success(f"저장 완료: {out_dir}")

    tabs = st.tabs(["레시피 카드", "촬영 가이드", "인스타", "블로그"])
    for tab, label, body, filename in zip(
        tabs,
        ["레시피 카드", "촬영 가이드", "인스타", "블로그"],
        [card_md, guide_md, insta_md, blog_md],
        ["00_recipe_card.json", "01_촬영가이드.md", "02_인스타.md", "03_블로그.md"],
    ):
        with tab:
            if filename.endswith(".json"):
                st.code(body, language="json")
            else:
                st.markdown(body)
            st.download_button(f"{label} 내려받기", body, file_name=filename)
