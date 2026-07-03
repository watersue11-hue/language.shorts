from __future__ import annotations

from pathlib import Path
import traceback

import streamlit as st


st.set_page_config(
    page_title="무료 다국어 학습 숏츠 생성기",
    page_icon="🎬",
    layout="centered",
)

FIXED_ILLUSTRATION_STYLE = "clean"

LANG_OPTIONS = {
    "스페인어": "es",
    "영어": "en",
    "일본어": "ja",
    "중국어": "zh",
    "프랑스어": "fr",
    "독일어": "de",
    "이탈리아어": "it",
}

THEME_OPTIONS = {
    "파란 카드형": "blue_card",
    "흰 배경 + 검정 글씨": "plain_white",
    "연회색 카드형": "soft_gray",
    "검정 배경 + 흰 글씨": "dark_clean",
}


def safe_import_generator():
    try:
        from free_video_generator import (
            VideoConfig,
            create_study_video,
            get_free_script,
            parse_manual_items,
        )
        return VideoConfig, create_study_video, get_free_script, parse_manual_items, None
    except Exception as e:
        return None, None, None, None, e


def fallback_manual_items(text: str):
    items = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0] and parts[1]:
            pronunciation = ""
            tip = "소리 내서 따라 해보세요"
            if len(parts) >= 4:
                pronunciation = parts[2]
                tip = parts[3] if parts[3] else tip
            elif len(parts) == 3:
                tip = parts[2] if parts[2] else tip
            items.append({"kr": parts[0], "target": parts[1], "pron": pronunciation, "tip": tip})
    return items


st.title("🎬 무료 다국어 학습 숏츠 생성기")
st.caption("무료 내장 표현/직접 입력 + 무료 gTTS 음성 + 테마 선택 + 인트로/발음 옵션으로 mp4를 만듭니다.")
st.success("앱 첫 화면 로드 완료")

with st.expander("이 버전 특징", expanded=False):
    st.markdown(
        """
        - OpenAI API를 사용하지 않습니다.
        - API Key 입력칸도 없습니다.
        - 인트로 카드를 넣을지 말지 선택할 수 있습니다.
        - 한국어 발음(한글 표기)을 표시할지 선택할 수 있습니다.
        - 테마를 4개 중에서 선택할 수 있습니다.
        - 자동 표현은 최대한 겹치지 않게 다양하게 구성되도록 확장했습니다.
        """
    )

with st.sidebar:
    st.header("영상 설정")

    selected_lang_name = st.selectbox("학습 언어", list(LANG_OPTIONS.keys()), index=0)
    target_lang = LANG_OPTIONS[selected_lang_name]

    is_shorts = st.radio("영상 비율", ["쇼츠 9:16", "롱폼 16:9"], index=0) == "쇼츠 9:16"

    max_words = 10 if is_shorts else 50
    default_words = 5 if is_shorts else 10
    words = st.slider("표현 개수", min_value=1, max_value=max_words, value=default_words, step=1)
    if is_shorts:
        st.caption("쇼츠는 1~10개까지 선택 가능합니다.")
    else:
        st.caption("롱폼은 1~50개까지 선택 가능합니다. 표현이 많을수록 렌더링 시간이 길어집니다.")

    shadowing_pause = st.slider("따라 말하기 간격", 1.0, 5.0, 2.2, 0.5)

    st.divider()
    st.header("표시 옵션")
    include_intro = st.checkbox("인트로 카드 넣기", value=False)
    show_pronunciation = st.checkbox("한국어 발음 표시", value=False)

    st.divider()
    st.header("음성 설정")
    use_tts = st.checkbox("무료 TTS 사용", value=True)
    slow_tts = st.checkbox("천천히 말하기", value=False)

    st.divider()
    st.header("배경 설정")
    use_illustration_bg = st.checkbox("테마 배경 사용", value=True, help="선택한 테마에 맞춰 배경과 글자 색을 적용합니다.")
    selected_theme_name = st.selectbox("화면 테마", list(THEME_OPTIONS.keys()), index=0)
    visual_theme = THEME_OPTIONS[selected_theme_name]

    st.info("체크하면 인트로 포함 버전, 끄면 인트로 없는 버전이 생성됩니다.")
    st.info("체크하면 외국어 표현 아래에 한국어 발음이 함께 표시됩니다.")

    use_bgm = st.checkbox("BGM 사용", value=Path("assets/bgm.mp3").exists())
    bgm_volume = st.slider("BGM 볼륨", 0.0, 0.25, 0.07, 0.01)

    use_bg_video = st.checkbox(
        "내 배경 영상 사용",
        value=Path("assets/bg_loop.mp4").exists(),
        help="assets/bg_loop.mp4가 있으면 테마 배경보다 우선 적용됩니다.",
    )

st.subheader("콘텐츠 입력")

topic = st.text_input(
    "영상 주제",
    placeholder="예: 공항, 카페, 여행, 학교, 쇼핑, 음식점, DM, 기본 회화",
)

source_mode = st.radio(
    "대본 방식",
    ["무료 내장 표현 자동 선택", "직접 입력"],
    horizontal=True,
)

items = []

if source_mode == "무료 내장 표현 자동 선택":
    if topic:
        _, _, get_free_script, _, import_error = safe_import_generator()
        if import_error is None:
            items = get_free_script(topic, target_lang, words)
        else:
            st.warning("영상 생성 모듈 import 전이라 기본 미리보기만 표시합니다. 생성 버튼을 누르면 오류를 자세히 표시합니다.")

        if items:
            st.markdown("#### 생성될 표현 미리보기")
            st.table(items)
        else:
            st.info("해당 주제에 맞는 표현을 준비 중입니다.")
    else:
        st.info("주제를 입력하면 표현 미리보기가 표시됩니다.")
else:
    st.markdown(
        """
        아래 형식으로 입력하세요.

        ```txt
        한국어 뜻 | 외국어 표현 | 짧은 설명
        안녕하세요 | Hola | 기본 인사
        감사합니다 | Gracias | 고마울 때 사용

        또는 발음까지 넣고 싶다면

        한국어 뜻 | 외국어 표현 | 한국어 발음 | 짧은 설명
        다시 말해 주세요 | Repítalo, por favor | 레피딸로 뽀르 파보르 | 못 들었을 때
        ```
        """
    )

    defaults = {
        "es": ("Hola", "Gracias", "Repítalo, por favor", "레피딸로 뽀르 파보르"),
        "en": ("Hello", "Thank you", "Could you say that again?", "쿠쥬 세이 댓 어게인"),
        "ja": ("こんにちは", "ありがとうございます", "もう一度言ってください", "모이치도 잇테 쿠다사이"),
        "zh": ("你好", "谢谢", "请再说一遍", "칭 짜이 슈오 이볜"),
        "fr": ("Bonjour", "Merci", "Répétez, s'il vous plaît", "헤뻬떼 실부플레"),
        "de": ("Hallo", "Danke", "Bitte sagen Sie das noch einmal", "비테 자겐 지 다스 노흐 아인말"),
        "it": ("Ciao", "Grazie", "Può ripetere, per favore?", "푸오 리페테레 페르 파보레"),
    }
    hello, thanks, repeat_text, repeat_pron = defaults.get(target_lang, defaults["en"])

    default_manual = f"""안녕하세요 | {hello} | 기본 인사
감사합니다 | {thanks} | 고마울 때 사용
다시 말해 주세요 | {repeat_text} | {repeat_pron} | 못 들었을 때"""
    manual_text = st.text_area("직접 입력", value=default_manual, height=220)

    _, _, _, parse_manual_items, import_error = safe_import_generator()
    if import_error is None:
        items = parse_manual_items(manual_text, target_lang)
    else:
        items = fallback_manual_items(manual_text)

    if items:
        st.markdown("#### 입력된 표현 미리보기")
        st.table(items)

if source_mode == "무료 내장 표현 자동 선택":
    st.caption("자동 선택은 주제별 표현을 우선 뽑고, 부족하면 다른 카테고리 표현을 겹치지 않게 합쳐서 보여줍니다.")
else:
    st.caption("직접 입력은 줄 수만큼 그대로 반영됩니다. 발음을 넣고 싶지 않으면 3칸 형식만 사용하면 됩니다.")

st.markdown("#### 배경 방식")
if use_bg_video and Path("assets/bg_loop.mp4").exists():
    st.info("assets/bg_loop.mp4를 배경 영상으로 사용합니다.")
elif use_illustration_bg:
    st.info(f"선택한 테마({selected_theme_name}) 배경을 사용합니다.")
else:
    st.info("단색 배경으로 제작합니다.")

generate = st.button("🔥 무료로 영상 생성하기", use_container_width=True)

if generate:
    if not topic.strip() and source_mode == "무료 내장 표현 자동 선택":
        st.error("주제를 입력하세요.")
        st.stop()

    if not items:
        st.error("생성할 표현이 없습니다.")
        st.stop()

    VideoConfig, create_study_video, get_free_script, parse_manual_items, import_error = safe_import_generator()

    if import_error is not None:
        st.error("영상 생성 모듈을 불러오지 못했습니다. 아래 오류를 확인하세요.")
        st.code("".join(traceback.format_exception(type(import_error), import_error, import_error.__traceback__)))
        st.stop()

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    cfg = VideoConfig(
        is_shorts=is_shorts,
        shadowing_pause=float(shadowing_pause),
        words_per_topic=int(words),
        output_dir=output_dir,
        target_lang=target_lang,
        use_tts=use_tts,
        slow_tts=slow_tts,
        use_illustration_bg=use_illustration_bg,
        illustration_style=FIXED_ILLUSTRATION_STYLE,
        visual_theme=visual_theme,
        include_intro=include_intro,
        show_pronunciation=show_pronunciation,
        bgm_path="assets/bgm.mp3" if use_bgm else None,
        bgm_volume=float(bgm_volume),
        bg_video_path="assets/bg_loop.mp4" if use_bg_video else None,
    )

    progress_box = st.empty()

    def ui_progress(message: str):
        progress_box.info(message)

    with st.status("영상 생성 중", expanded=True) as status:
        try:
            output_path = create_study_video(
                topic=topic.strip() or "manual",
                items=items[:words],
                cfg=cfg,
                progress_callback=ui_progress,
            )
            status.update(label="영상 생성 완료", state="complete", expanded=False)

            st.success("완성됐습니다.")
            st.subheader("미리보기")
            st.video(str(output_path))

            with open(output_path, "rb") as f:
                st.download_button(
                    label="📥 mp4 다운로드",
                    data=f,
                    file_name=output_path.name,
                    mime="video/mp4",
                    use_container_width=True,
                )

        except Exception as e:
            status.update(label="영상 생성 실패", state="error", expanded=True)
            st.exception(e)
            st.error("오류가 났습니다. 그래도 유료 API 비용은 발생하지 않습니다.")
