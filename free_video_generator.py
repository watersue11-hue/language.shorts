from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from moviepy import (
        AudioClip,
        AudioFileClip,
        ColorClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_audioclips,
        concatenate_videoclips,
    )
except ImportError:
    from moviepy.editor import (
        AudioFileClip,
        ColorClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_audioclips,
        concatenate_videoclips,
    )
    from moviepy.audio.AudioClip import AudioClip


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("free_language_shorts")

AUDIO_CACHE_DIR = Path(".audio_cache_free")


LANG_OPTIONS = {
    "스페인어": "es",
    "영어": "en",
    "일본어": "ja",
    "중국어": "zh",
    "프랑스어": "fr",
    "독일어": "de",
    "이탈리아어": "it",
}

LANG_DISPLAY_NAMES: Dict[str, str] = {
    "ko": "한국어",
    "es": "스페인어",
    "en": "영어",
    "ja": "일본어",
    "zh": "중국어",
    "fr": "프랑스어",
    "de": "독일어",
    "it": "이탈리아어",
}

GTTS_LANG: Dict[str, str] = {
    "ko": "ko",
    "es": "es",
    "en": "en",
    "ja": "ja",
    "zh": "zh-CN",
    "fr": "fr",
    "de": "de",
    "it": "it",
}


LANG_FONT_CANDIDATES: Dict[str, List[str]] = {
    "ko": [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgunbd.ttf",
        "/System/Library/Fonts/Supplemental/AppleSDGothicNeo.ttc",
    ],
    "ja": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    ],
    "zh": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ],
    "en": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
}
for _latin_lang in ["es", "fr", "de", "it"]:
    LANG_FONT_CANDIDATES[_latin_lang] = LANG_FONT_CANDIDATES["en"]


FREE_PHRASES: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "es": {
        "기본": [
            {"kr": "안녕하세요", "target": "Hola", "tip": "가장 기본적인 인사"},
            {"kr": "감사합니다", "target": "Gracias", "tip": "고마울 때 사용"},
            {"kr": "천만에요", "target": "De nada", "tip": "대답으로 자연스러움"},
            {"kr": "실례합니다", "target": "Disculpe", "tip": "말을 걸 때 사용"},
            {"kr": "다시 말해 주세요", "target": "Repítalo, por favor", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "Está bien", "tip": "문제없다는 느낌"},
            {"kr": "좋아요", "target": "Me gusta", "tip": "마음에 들 때"},
            {"kr": "잘 모르겠어요", "target": "No lo sé", "tip": "모를 때 사용"},
        ],
        "공항": [
            {"kr": "여권 여기 있습니다", "target": "Aquí tiene mi pasaporte", "tip": "입국 심사에서"},
            {"kr": "관광하러 왔어요", "target": "Vengo de turismo", "tip": "방문 목적 설명"},
            {"kr": "며칠 머무르세요?", "target": "¿Cuántos días se queda?", "tip": "체류 기간 질문"},
            {"kr": "일주일 머물 거예요", "target": "Me quedo una semana", "tip": "체류 기간 대답"},
            {"kr": "짐은 어디서 찾나요?", "target": "¿Dónde recojo mi equipaje?", "tip": "수하물 찾을 때"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "Un café, por favor", "tip": "가장 간단한 주문"},
            {"kr": "아이스로 주세요", "target": "Con hielo, por favor", "tip": "얼음 요청"},
            {"kr": "포장해 주세요", "target": "Para llevar, por favor", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "¿Cuánto cuesta?", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "¿Aceptan tarjeta?", "tip": "카드 결제 확인"},
        ],
        "여행": [
            {"kr": "여기 어떻게 가요?", "target": "¿Cómo llego aquí?", "tip": "길 물을 때"},
            {"kr": "역이 어디예요?", "target": "¿Dónde está la estación?", "tip": "장소 찾기"},
            {"kr": "사진 찍어 주세요", "target": "¿Puede tomarme una foto?", "tip": "여행 필수 표현"},
            {"kr": "추천해 주세요", "target": "¿Qué me recomienda?", "tip": "추천 요청"},
            {"kr": "화장실 어디예요?", "target": "¿Dónde está el baño?", "tip": "급할 때 필수"},
        ],
    },
    "en": {
        "기본": [
            {"kr": "안녕하세요", "target": "Hello", "tip": "가장 기본적인 인사"},
            {"kr": "감사합니다", "target": "Thank you", "tip": "고마울 때 사용"},
            {"kr": "천만에요", "target": "You're welcome", "tip": "감사 인사 대답"},
            {"kr": "실례합니다", "target": "Excuse me", "tip": "말 걸 때 사용"},
            {"kr": "다시 말해 주세요", "target": "Could you say that again?", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "It's okay", "tip": "문제없다는 느낌"},
            {"kr": "좋아요", "target": "I like it", "tip": "마음에 들 때"},
            {"kr": "잘 모르겠어요", "target": "I'm not sure", "tip": "모를 때 부드럽게"},
        ],
        "공항": [
            {"kr": "여권 여기 있습니다", "target": "Here is my passport", "tip": "입국 심사에서"},
            {"kr": "관광하러 왔어요", "target": "I'm here for tourism", "tip": "방문 목적 설명"},
            {"kr": "며칠 머무르세요?", "target": "How long will you stay?", "tip": "체류 기간 질문"},
            {"kr": "일주일 머물 거예요", "target": "I'll stay for a week", "tip": "체류 기간 대답"},
            {"kr": "짐은 어디서 찾나요?", "target": "Where can I get my luggage?", "tip": "수하물 찾을 때"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "Can I get a coffee?", "tip": "자연스러운 주문"},
            {"kr": "아이스로 주세요", "target": "Can I get it iced?", "tip": "아이스 요청"},
            {"kr": "포장해 주세요", "target": "To go, please", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "How much is it?", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "Do you take cards?", "tip": "카드 결제 확인"},
        ],
        "DM": [
            {"kr": "답장 늦어서 미안", "target": "Sorry for the late reply", "tip": "DM 답장 시작"},
            {"kr": "진짜 웃기다", "target": "That's so funny", "tip": "리액션 표현"},
            {"kr": "나도 그렇게 생각해", "target": "I feel the same way", "tip": "공감할 때"},
            {"kr": "오늘 어땠어?", "target": "How was your day?", "tip": "가볍게 묻기"},
            {"kr": "완전 좋아", "target": "I love it", "tip": "강한 긍정"},
        ],
    },
    "ja": {
        "기본": [
            {"kr": "안녕하세요", "target": "こんにちは", "tip": "낮 시간 기본 인사"},
            {"kr": "감사합니다", "target": "ありがとうございます", "tip": "정중한 감사 표현"},
            {"kr": "천만에요", "target": "どういたしまして", "tip": "감사 인사 대답"},
            {"kr": "실례합니다", "target": "すみません", "tip": "말 걸거나 사과할 때"},
            {"kr": "다시 말해 주세요", "target": "もう一度言ってください", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "大丈夫です", "tip": "괜찮다는 표현"},
            {"kr": "좋아요", "target": "いいですね", "tip": "긍정 리액션"},
            {"kr": "잘 모르겠어요", "target": "よくわかりません", "tip": "모를 때 사용"},
        ],
        "공항": [
            {"kr": "여권 여기 있습니다", "target": "パスポートはこちらです", "tip": "입국 심사에서"},
            {"kr": "관광하러 왔어요", "target": "観光で来ました", "tip": "방문 목적 설명"},
            {"kr": "며칠 머무르세요?", "target": "何日滞在しますか？", "tip": "체류 기간 질문"},
            {"kr": "일주일 머물 거예요", "target": "一週間滞在します", "tip": "체류 기간 대답"},
            {"kr": "짐은 어디서 찾나요?", "target": "荷物はどこで受け取れますか？", "tip": "수하물 찾을 때"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "コーヒーを一つください", "tip": "기본 주문"},
            {"kr": "아이스로 주세요", "target": "アイスでお願いします", "tip": "아이스 요청"},
            {"kr": "포장해 주세요", "target": "持ち帰りでお願いします", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "いくらですか？", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "カードは使えますか？", "tip": "카드 결제 확인"},
        ],
    },
    "zh": {
        "기본": [
            {"kr": "안녕하세요", "target": "你好", "tip": "가장 기본적인 인사"},
            {"kr": "감사합니다", "target": "谢谢", "tip": "고마울 때 사용"},
            {"kr": "천만에요", "target": "不客气", "tip": "감사 인사 대답"},
            {"kr": "실례합니다", "target": "打扰一下", "tip": "말 걸 때 자연스러움"},
            {"kr": "다시 말해 주세요", "target": "请再说一遍", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "没关系", "tip": "문제없다는 표현"},
            {"kr": "좋아요", "target": "很好", "tip": "긍정 리액션"},
            {"kr": "잘 모르겠어요", "target": "我不太清楚", "tip": "모를 때 부드럽게"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "请给我一杯咖啡", "tip": "기본 주문"},
            {"kr": "아이스로 주세요", "target": "请加冰", "tip": "얼음 요청"},
            {"kr": "포장해 주세요", "target": "请打包", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "多少钱？", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "可以刷卡吗？", "tip": "카드 결제 확인"},
        ],
        "여행": [
            {"kr": "여기 어떻게 가요?", "target": "这里怎么走？", "tip": "길 물을 때"},
            {"kr": "역이 어디예요?", "target": "车站在哪里？", "tip": "장소 찾기"},
            {"kr": "사진 찍어 주세요", "target": "可以帮我拍照吗？", "tip": "여행 필수 표현"},
            {"kr": "추천해 주세요", "target": "你有什么推荐？", "tip": "추천 요청"},
            {"kr": "화장실 어디예요?", "target": "洗手间在哪里？", "tip": "급할 때 필수"},
        ],
    },
}

FREE_PHRASES["fr"] = {
    "기본": [
        {"kr": "안녕하세요", "target": "Bonjour", "tip": "기본 인사"},
        {"kr": "감사합니다", "target": "Merci", "tip": "고마울 때 사용"},
        {"kr": "실례합니다", "target": "Excusez-moi", "tip": "말 걸 때 사용"},
        {"kr": "얼마예요?", "target": "C'est combien ?", "tip": "가격 질문"},
        {"kr": "다시 말해 주세요", "target": "Répétez, s'il vous plaît", "tip": "못 들었을 때"},
    ]
}
FREE_PHRASES["de"] = {
    "기본": [
        {"kr": "안녕하세요", "target": "Hallo", "tip": "기본 인사"},
        {"kr": "감사합니다", "target": "Danke", "tip": "고마울 때 사용"},
        {"kr": "실례합니다", "target": "Entschuldigung", "tip": "말 걸 때 사용"},
        {"kr": "얼마예요?", "target": "Wie viel kostet das?", "tip": "가격 질문"},
        {"kr": "다시 말해 주세요", "target": "Bitte sagen Sie das noch einmal", "tip": "못 들었을 때"},
    ]
}
FREE_PHRASES["it"] = {
    "기본": [
        {"kr": "안녕하세요", "target": "Ciao", "tip": "가벼운 인사"},
        {"kr": "감사합니다", "target": "Grazie", "tip": "고마울 때 사용"},
        {"kr": "실례합니다", "target": "Mi scusi", "tip": "말 걸 때 사용"},
        {"kr": "얼마예요?", "target": "Quanto costa?", "tip": "가격 질문"},
        {"kr": "다시 말해 주세요", "target": "Può ripetere?", "tip": "못 들었을 때"},
    ]
}




def _dedupe_phrase_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out = []
    for item in items:
        key = (item.get("kr", "").strip(), item.get("target", "").strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


EXTRA_FREE_PHRASES: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "es": {
        "기본": [
            {"kr": "죄송합니다", "target": "Lo siento", "pron": "로 씨엔또", "tip": "사과할 때"},
            {"kr": "도와주세요", "target": "Ayúdeme, por favor", "pron": "아유데메 뽀르 파보르", "tip": "도움이 필요할 때"},
            {"kr": "천천히 말씀해 주세요", "target": "Hable más despacio, por favor", "pron": "아블레 마스 데스빠시오 뽀르 파보르", "tip": "속도가 빠를 때"},
            {"kr": "이해했어요", "target": "Entendí", "pron": "엔뗀디", "tip": "이해했을 때"},
            {"kr": "이해 못 했어요", "target": "No entendí", "pron": "노 엔뗀디", "tip": "이해 못 했을 때"},
            {"kr": "잠시만요", "target": "Un momento", "pron": "운 모멘또", "tip": "잠깐 멈춰 달라고 할 때"},
            {"kr": "어디예요?", "target": "¿Dónde está?", "pron": "돈데 에스타", "tip": "위치 물을 때"},
            {"kr": "지금 가능해요?", "target": "¿Es posible ahora?", "pron": "에스 뽀씨블레 아오라", "tip": "가능 여부 확인"},
            {"kr": "반가워요", "target": "Mucho gusto", "pron": "무초 구스또", "tip": "첫 만남 인사"},
            {"kr": "오늘 어때요?", "target": "¿Cómo estás hoy?", "pron": "꼬모 에스타스 오이", "tip": "가볍게 안부 묻기"},
        ],
        "학교": [
            {"kr": "수업이 몇 시예요?", "target": "¿A qué hora es la clase?", "pron": "아 께 오라 에스 라 끌라세", "tip": "수업 시간 질문"},
            {"kr": "과제를 제출했어요", "target": "Entregué la tarea", "pron": "엔뜨레게 라 따레아", "tip": "과제 제출 말하기"},
            {"kr": "시험이 어려웠어요", "target": "El examen fue difícil", "pron": "엘 엑사멘 푸에 디피실", "tip": "시험 후 대화"},
            {"kr": "도서관은 어디예요?", "target": "¿Dónde está la biblioteca?", "pron": "돈데 에스타 라 비블리오떼까", "tip": "학교 시설 찾기"},
            {"kr": "같이 공부할래요?", "target": "¿Quieres estudiar juntos?", "pron": "끼에레스 에스뚜디아르 훈또스", "tip": "스터디 제안"},
        ],
        "쇼핑": [
            {"kr": "다른 색 있나요?", "target": "¿Tiene otro color?", "pron": "띠에네 오뜨로 꼴로르", "tip": "색상 질문"},
            {"kr": "입어봐도 되나요?", "target": "¿Puedo probármelo?", "pron": "뿌에도 프로바르멜로", "tip": "피팅 요청"},
            {"kr": "이거 할인돼요?", "target": "¿Tiene descuento?", "pron": "띠에네 데스꿴또", "tip": "할인 여부 질문"},
            {"kr": "영수증 주세요", "target": "Deme el recibo, por favor", "pron": "데메 엘 레씨보 뽀르 파보르", "tip": "결제 후"},
            {"kr": "이 사이즈 있나요?", "target": "¿Tiene esta talla?", "pron": "띠에네 에스타 따야", "tip": "사이즈 질문"},
        ],
    },
    "en": {
        "기본": [
            {"kr": "죄송합니다", "target": "I'm sorry", "pron": "아임 쏘리", "tip": "사과할 때"},
            {"kr": "도와주세요", "target": "Please help me", "pron": "플리즈 헬프 미", "tip": "도움이 필요할 때"},
            {"kr": "천천히 말해 주세요", "target": "Please speak slowly", "pron": "플리즈 스피크 슬로울리", "tip": "속도가 빠를 때"},
            {"kr": "이해했어요", "target": "I got it", "pron": "아이 갓 잇", "tip": "이해했을 때"},
            {"kr": "이해 못 했어요", "target": "I don't understand", "pron": "아이 돈 언더스탠드", "tip": "이해 못 했을 때"},
            {"kr": "잠시만요", "target": "Just a moment", "pron": "저스트 어 모먼트", "tip": "잠깐 멈춰 달라고 할 때"},
            {"kr": "어디예요?", "target": "Where is it?", "pron": "웨어 이즈 잇", "tip": "위치 물을 때"},
            {"kr": "지금 가능해요?", "target": "Is it possible now?", "pron": "이즈 잇 파서블 나우", "tip": "가능 여부 확인"},
            {"kr": "반가워요", "target": "Nice to meet you", "pron": "나이스 투 밋 유", "tip": "첫 만남 인사"},
            {"kr": "오늘 어때요?", "target": "How are you today?", "pron": "하우 아 유 투데이", "tip": "가볍게 안부 묻기"},
        ],
        "학교": [
            {"kr": "수업이 몇 시예요?", "target": "What time is the class?", "pron": "왓 타임 이즈 더 클래스", "tip": "수업 시간 질문"},
            {"kr": "과제를 제출했어요", "target": "I turned in the assignment", "pron": "아이 턴드 인 디 어사인먼트", "tip": "과제 제출 말하기"},
            {"kr": "시험이 어려웠어요", "target": "The exam was hard", "pron": "디 이그잼 워즈 하드", "tip": "시험 후 대화"},
            {"kr": "도서관은 어디예요?", "target": "Where is the library?", "pron": "웨어 이즈 더 라이브러리", "tip": "학교 시설 찾기"},
            {"kr": "같이 공부할래요?", "target": "Do you want to study together?", "pron": "두 유 원트 투 스터디 투게더", "tip": "스터디 제안"},
        ],
        "쇼핑": [
            {"kr": "다른 색 있나요?", "target": "Do you have another color?", "pron": "두 유 해브 어나더 컬러", "tip": "색상 질문"},
            {"kr": "입어봐도 되나요?", "target": "Can I try this on?", "pron": "캔 아이 트라이 디스 온", "tip": "피팅 요청"},
            {"kr": "이거 할인돼요?", "target": "Is this on sale?", "pron": "이즈 디스 온 세일", "tip": "할인 여부 질문"},
            {"kr": "영수증 주세요", "target": "Can I get the receipt?", "pron": "캔 아이 겟 더 리싯", "tip": "결제 후"},
            {"kr": "이 사이즈 있나요?", "target": "Do you have this size?", "pron": "두 유 해브 디스 사이즈", "tip": "사이즈 질문"},
        ],
    },
    "ja": {
        "기본": [
            {"kr": "죄송합니다", "target": "ごめんなさい", "pron": "고멘나사이", "tip": "사과할 때"},
            {"kr": "도와주세요", "target": "助けてください", "pron": "다스케테 쿠다사이", "tip": "도움이 필요할 때"},
            {"kr": "천천히 말해 주세요", "target": "ゆっくり話してください", "pron": "윳쿠리 하나시테 쿠다사이", "tip": "속도가 빠를 때"},
            {"kr": "이해했어요", "target": "わかりました", "pron": "와카리마시타", "tip": "이해했을 때"},
            {"kr": "이해 못 했어요", "target": "わかりませんでした", "pron": "와카리마센데시타", "tip": "이해 못 했을 때"},
            {"kr": "잠시만요", "target": "ちょっと待ってください", "pron": "촛토 맛테 쿠다사이", "tip": "잠깐 멈춰 달라고 할 때"},
            {"kr": "어디예요?", "target": "どこですか？", "pron": "도코데스카", "tip": "위치 물을 때"},
            {"kr": "지금 가능해요?", "target": "今、大丈夫ですか？", "pron": "이마 다이조부데스카", "tip": "가능 여부 확인"},
            {"kr": "반가워요", "target": "はじめまして", "pron": "하지메마시테", "tip": "첫 만남 인사"},
            {"kr": "오늘 어때요?", "target": "今日はどうですか？", "pron": "쿄와 도우데스카", "tip": "가볍게 안부 묻기"},
        ],
        "학교": [
            {"kr": "수업이 몇 시예요?", "target": "授業は何時ですか？", "pron": "주교와 난지데스카", "tip": "수업 시간 질문"},
            {"kr": "과제를 제출했어요", "target": "課題を提出しました", "pron": "카다이오 테이슈츠시마시타", "tip": "과제 제출 말하기"},
            {"kr": "시험이 어려웠어요", "target": "試験は難しかったです", "pron": "시켄와 무즈카시캇타데스", "tip": "시험 후 대화"},
            {"kr": "도서관은 어디예요?", "target": "図書館はどこですか？", "pron": "토쇼칸와 도코데스카", "tip": "학교 시설 찾기"},
            {"kr": "같이 공부할래요?", "target": "一緒に勉強しませんか？", "pron": "잇쇼니 벤쿄시마센카", "tip": "스터디 제안"},
        ],
        "쇼핑": [
            {"kr": "다른 색 있나요?", "target": "他の色はありますか？", "pron": "호카노 이로와 아리마스카", "tip": "색상 질문"},
            {"kr": "입어봐도 되나요?", "target": "試着してもいいですか？", "pron": "시챠쿠시테모 이이데스카", "tip": "피팅 요청"},
            {"kr": "이거 할인돼요?", "target": "これは割引ですか？", "pron": "코레와 와리비키데스카", "tip": "할인 여부 질문"},
            {"kr": "영수증 주세요", "target": "レシートをください", "pron": "레시토오 쿠다사이", "tip": "결제 후"},
            {"kr": "이 사이즈 있나요?", "target": "このサイズはありますか？", "pron": "코노 사이즈와 아리마스카", "tip": "사이즈 질문"},
        ],
    },
    "zh": {
        "기본": [
            {"kr": "죄송합니다", "target": "对不起", "pron": "뚜이부치", "tip": "사과할 때"},
            {"kr": "도와주세요", "target": "请帮帮我", "pron": "칭빵빵워", "tip": "도움이 필요할 때"},
            {"kr": "천천히 말해 주세요", "target": "请说慢一点", "pron": "칭 슈오 만 이뎬", "tip": "속도가 빠를 때"},
            {"kr": "이해했어요", "target": "我明白了", "pron": "워 밍바이 러", "tip": "이해했을 때"},
            {"kr": "이해 못 했어요", "target": "我没听懂", "pron": "워 메이 팅동", "tip": "이해 못 했을 때"},
            {"kr": "잠시만요", "target": "请等一下", "pron": "칭 덩 이샤", "tip": "잠깐 멈춰 달라고 할 때"},
            {"kr": "어디예요?", "target": "在哪里？", "pron": "짜이 나리", "tip": "위치 물을 때"},
            {"kr": "지금 가능해요?", "target": "现在可以吗？", "pron": "시앤짜이 커이 마", "tip": "가능 여부 확인"},
            {"kr": "반가워요", "target": "很高兴认识你", "pron": "헌 가오싱 런스 니", "tip": "첫 만남 인사"},
            {"kr": "오늘 어때요?", "target": "你今天怎么样？", "pron": "니 진티앤 쩐머양", "tip": "가볍게 안부 묻기"},
        ],
        "학교": [
            {"kr": "수업이 몇 시예요?", "target": "几点上课？", "pron": "지디앤 샹커", "tip": "수업 시간 질문"},
            {"kr": "과제를 제출했어요", "target": "我提交作业了", "pron": "워 티자오 쭈어예 러", "tip": "과제 제출 말하기"},
            {"kr": "시험이 어려웠어요", "target": "考试很难", "pron": "카오스 헌 난", "tip": "시험 후 대화"},
            {"kr": "도서관은 어디예요?", "target": "图书馆在哪里？", "pron": "투슈관 짜이 나리", "tip": "학교 시설 찾기"},
            {"kr": "같이 공부할래요?", "target": "一起学习吗？", "pron": "이치 쉐시 마", "tip": "스터디 제안"},
        ],
        "쇼핑": [
            {"kr": "다른 색 있나요?", "target": "有别的颜色吗？", "pron": "요우 비에더 옌써 마", "tip": "색상 질문"},
            {"kr": "입어봐도 되나요?", "target": "可以试穿吗？", "pron": "커이 스촨 마", "tip": "피팅 요청"},
            {"kr": "이거 할인돼요?", "target": "这个打折吗？", "pron": "저거 다저 마", "tip": "할인 여부 질문"},
            {"kr": "영수증 주세요", "target": "请给我发票", "pron": "칭 게이워 파피아오", "tip": "결제 후"},
            {"kr": "이 사이즈 있나요?", "target": "有这个尺码吗？", "pron": "요우 저거 츠마 마", "tip": "사이즈 질문"},
        ],
    },
}


def _apply_extra_free_phrases() -> None:
    for lang, topics in EXTRA_FREE_PHRASES.items():
        lang_bank = FREE_PHRASES.setdefault(lang, {})
        for topic_name, extra_items in topics.items():
            current = list(lang_bank.get(topic_name, []))
            current.extend(extra_items)
            lang_bank[topic_name] = _dedupe_phrase_items(current)

    for lang, topics in FREE_PHRASES.items():
        for topic_name, items in list(topics.items()):
            normalized = []
            for item in items:
                new_item = dict(item)
                if "pron" not in new_item:
                    if lang in ["en", "es", "fr", "de", "it"]:
                        new_item["pron"] = new_item.get("target", "")
                    else:
                        new_item["pron"] = ""
                normalized.append(new_item)
            topics[topic_name] = _dedupe_phrase_items(normalized)


_apply_extra_free_phrases()


RICH_EXTRA_PHRASES: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "es": {
        "자기소개": [
            {"kr": "제 이름은 민지예요", "target": "Me llamo Minji", "pron": "메 야모 민지", "tip": "이름 소개"},
            {"kr": "저는 한국에서 왔어요", "target": "Soy de Corea", "pron": "소이 데 코레아", "tip": "출신 소개"},
            {"kr": "대학교에 다니고 있어요", "target": "Voy a la universidad", "pron": "보이 아 라 우니베르시다드", "tip": "학생 소개"},
            {"kr": "제 전공은 공학이에요", "target": "Mi especialidad es ingeniería", "pron": "미 에스페시아리다드 에스 인헤니에리아", "tip": "전공 소개"},
            {"kr": "만나서 반가워요", "target": "Mucho gusto", "pron": "무초 구스또", "tip": "처음 만났을 때"},
            {"kr": "취미는 여행이에요", "target": "Mi hobby es viajar", "pron": "미 오비 에스 비아하르", "tip": "취미 소개"},
        ],
        "음식점": [
            {"kr": "메뉴 좀 볼 수 있을까요?", "target": "¿Puedo ver el menú?", "pron": "뿌에도 베르 엘 메누", "tip": "메뉴 요청"},
            {"kr": "이거 추천해 주세요", "target": "¿Me recomienda esto?", "pron": "메 레꼬미엔다 에스또", "tip": "추천 요청"},
            {"kr": "덜 맵게 해 주세요", "target": "Menos picante, por favor", "pron": "메노스 삐깐떼 뽀르 파보르", "tip": "맛 조절 요청"},
            {"kr": "물 한 잔 주세요", "target": "Agua, por favor", "pron": "아구아 뽀르 파보르", "tip": "물 요청"},
            {"kr": "계산서 주세요", "target": "La cuenta, por favor", "pron": "라 꾸엔따 뽀르 파보르", "tip": "계산 요청"},
        ],
        "교통": [
            {"kr": "이 버스는 시내로 가나요?", "target": "¿Este autobús va al centro?", "pron": "에스떼 아우또부스 바 알 센뜨로", "tip": "버스 노선 확인"},
            {"kr": "택시를 불러 주세요", "target": "Llámeme un taxi, por favor", "pron": "야메메 운 딱시 뽀르 파보르", "tip": "택시 요청"},
            {"kr": "다음 역이 어디예요?", "target": "¿Cuál es la próxima estación?", "pron": "꾸알 에스 라 프록시마 에스타시온", "tip": "지하철 이동"},
            {"kr": "여기서 내려 주세요", "target": "Déjeme aquí, por favor", "pron": "데헤메 아끼 뽀르 파보르", "tip": "하차 요청"},
            {"kr": "얼마나 걸려요?", "target": "¿Cuánto tarda?", "pron": "꾸안또 따르다", "tip": "소요 시간 질문"},
        ],
        "숙소": [
            {"kr": "체크인하고 싶어요", "target": "Quiero hacer el check-in", "pron": "끼에로 아세르 엘 체크인", "tip": "호텔 체크인"},
            {"kr": "예약했어요", "target": "Tengo una reserva", "pron": "뗑고 우나 레세르바", "tip": "예약 확인"},
            {"kr": "와이파이 비밀번호가 뭐예요?", "target": "¿Cuál es la contraseña del wifi?", "pron": "꾸알 에스 라 꼰뜨라세냐 델 와이파이", "tip": "와이파이 문의"},
            {"kr": "수건 좀 더 주세요", "target": "Necesito más toallas", "pron": "네세씨또 마스 또아야스", "tip": "추가 요청"},
            {"kr": "체크아웃은 몇 시예요?", "target": "¿A qué hora es el check-out?", "pron": "아 께 오라 에스 엘 체크아웃", "tip": "체크아웃 시간 문의"},
        ],
        "병원": [
            {"kr": "머리가 아파요", "target": "Me duele la cabeza", "pron": "메 두엘레 라 까베사", "tip": "증상 설명"},
            {"kr": "약국이 어디예요?", "target": "¿Dónde está la farmacia?", "pron": "돈데 에스타 라 파르마시아", "tip": "약국 찾기"},
            {"kr": "의사를 만나고 싶어요", "target": "Quiero ver a un médico", "pron": "끼에로 베르 아 운 메디꼬", "tip": "진료 요청"},
            {"kr": "알레르기가 있어요", "target": "Tengo alergia", "pron": "뗑고 알레르히아", "tip": "알레르기 설명"},
            {"kr": "응급실로 가야 하나요?", "target": "¿Debo ir a urgencias?", "pron": "데보 이르 아 우르헨시아스", "tip": "응급 여부 확인"},
        ],
        "비즈니스": [
            {"kr": "회의는 몇 시에 시작하나요?", "target": "¿A qué hora empieza la reunión?", "pron": "아 께 오라 엠피에사 라 레우니온", "tip": "회의 시간 확인"},
            {"kr": "이메일로 보내 드릴게요", "target": "Se lo enviaré por correo", "pron": "세 로 엔비아레 뽀르 꼬레오", "tip": "이메일 안내"},
            {"kr": "자료를 공유해 주세요", "target": "Comparta el material, por favor", "pron": "꼼빠르따 엘 마떼리알 뽀르 파보르", "tip": "자료 요청"},
            {"kr": "잠시 검토할 시간이 필요해요", "target": "Necesito tiempo para revisarlo", "pron": "네세씨또 띠엠뽀 빠라 레비사를로", "tip": "검토 요청"},
            {"kr": "다음 주에 다시 이야기해요", "target": "Hablemos de nuevo la próxima semana", "pron": "아블레모스 데 누에보 라 프로시마 세마나", "tip": "후속 일정"},
        ],
    },
    "en": {
        "자기소개": [
            {"kr": "제 이름은 민지예요", "target": "My name is Minji", "pron": "마이 네임 이즈 민지", "tip": "이름 소개"},
            {"kr": "저는 한국에서 왔어요", "target": "I'm from Korea", "pron": "아임 프럼 코리아", "tip": "출신 소개"},
            {"kr": "대학교에 다니고 있어요", "target": "I go to university", "pron": "아이 고 투 유니버시티", "tip": "학생 소개"},
            {"kr": "제 전공은 공학이에요", "target": "My major is engineering", "pron": "마이 메이저 이즈 엔지니어링", "tip": "전공 소개"},
            {"kr": "만나서 반가워요", "target": "Nice to meet you", "pron": "나이스 투 밋 유", "tip": "처음 만났을 때"},
            {"kr": "취미는 여행이에요", "target": "My hobby is traveling", "pron": "마이 하비 이즈 트래블링", "tip": "취미 소개"},
        ],
        "음식점": [
            {"kr": "메뉴 좀 볼 수 있을까요?", "target": "May I see the menu?", "pron": "메이 아이 씨 더 메뉴", "tip": "메뉴 요청"},
            {"kr": "이거 추천해 주세요", "target": "What do you recommend?", "pron": "왓 두 유 레커멘드", "tip": "추천 요청"},
            {"kr": "덜 맵게 해 주세요", "target": "Please make it less spicy", "pron": "플리즈 메이크 잇 레스 스파이시", "tip": "맛 조절 요청"},
            {"kr": "물 한 잔 주세요", "target": "Can I get a glass of water?", "pron": "캔 아이 겟 어 글래스 오브 워터", "tip": "물 요청"},
            {"kr": "계산서 주세요", "target": "Could I get the bill?", "pron": "쿠드 아이 겟 더 빌", "tip": "계산 요청"},
        ],
        "교통": [
            {"kr": "이 버스는 시내로 가나요?", "target": "Does this bus go downtown?", "pron": "더즈 디스 버스 고 다운타운", "tip": "버스 노선 확인"},
            {"kr": "택시를 불러 주세요", "target": "Could you call a taxi for me?", "pron": "쿠쥬 콜 어 택시 포 미", "tip": "택시 요청"},
            {"kr": "다음 역이 어디예요?", "target": "What is the next station?", "pron": "왓 이즈 더 넥스트 스테이션", "tip": "지하철 이동"},
            {"kr": "여기서 내려 주세요", "target": "Please let me off here", "pron": "플리즈 렛 미 오프 히어", "tip": "하차 요청"},
            {"kr": "얼마나 걸려요?", "target": "How long does it take?", "pron": "하우 롱 더즈 잇 테이크", "tip": "소요 시간 질문"},
        ],
        "숙소": [
            {"kr": "체크인하고 싶어요", "target": "I'd like to check in", "pron": "아이드 라이크 투 체크 인", "tip": "호텔 체크인"},
            {"kr": "예약했어요", "target": "I have a reservation", "pron": "아이 해브 어 레저베이션", "tip": "예약 확인"},
            {"kr": "와이파이 비밀번호가 뭐예요?", "target": "What's the Wi-Fi password?", "pron": "왓츠 더 와이파이 패스워드", "tip": "와이파이 문의"},
            {"kr": "수건 좀 더 주세요", "target": "Could I get more towels?", "pron": "쿠드 아이 겟 모어 타월즈", "tip": "추가 요청"},
            {"kr": "체크아웃은 몇 시예요?", "target": "What time is check-out?", "pron": "왓 타임 이즈 체크아웃", "tip": "체크아웃 시간 문의"},
        ],
        "병원": [
            {"kr": "머리가 아파요", "target": "I have a headache", "pron": "아이 해브 어 헤드에이크", "tip": "증상 설명"},
            {"kr": "약국이 어디예요?", "target": "Where is the pharmacy?", "pron": "웨어 이즈 더 파머시", "tip": "약국 찾기"},
            {"kr": "의사를 만나고 싶어요", "target": "I'd like to see a doctor", "pron": "아이드 라이크 투 씨 어 닥터", "tip": "진료 요청"},
            {"kr": "알레르기가 있어요", "target": "I have an allergy", "pron": "아이 해브 언 앨러지", "tip": "알레르기 설명"},
            {"kr": "응급실로 가야 하나요?", "target": "Do I need to go to the ER?", "pron": "두 아이 니드 투 고 투 디 이알", "tip": "응급 여부 확인"},
        ],
        "비즈니스": [
            {"kr": "회의는 몇 시에 시작하나요?", "target": "What time does the meeting start?", "pron": "왓 타임 더즈 더 미팅 스타트", "tip": "회의 시간 확인"},
            {"kr": "이메일로 보내 드릴게요", "target": "I'll send it by email", "pron": "아일 센드 잇 바이 이메일", "tip": "이메일 안내"},
            {"kr": "자료를 공유해 주세요", "target": "Please share the materials", "pron": "플리즈 셰어 더 머티어리얼즈", "tip": "자료 요청"},
            {"kr": "잠시 검토할 시간이 필요해요", "target": "I need some time to review it", "pron": "아이 니드 섬 타임 투 리뷰 잇", "tip": "검토 요청"},
            {"kr": "다음 주에 다시 이야기해요", "target": "Let's talk again next week", "pron": "렛츠 톡 어게인 넥스트 위크", "tip": "후속 일정"},
        ],
    },
    "ja": {
        "자기소개": [
            {"kr": "제 이름은 민지예요", "target": "私の名前はミンジです", "pron": "와타시노 나마에와 민지데스", "tip": "이름 소개"},
            {"kr": "저는 한국에서 왔어요", "target": "韓国から来ました", "pron": "칸코쿠카라 키마시타", "tip": "출신 소개"},
            {"kr": "대학교에 다니고 있어요", "target": "大学に通っています", "pron": "다이가쿠니 카욧테이마스", "tip": "학생 소개"},
            {"kr": "제 전공은 공학이에요", "target": "専攻は工学です", "pron": "센코와 코가쿠데스", "tip": "전공 소개"},
            {"kr": "만나서 반가워요", "target": "お会いできてうれしいです", "pron": "오아이데키테 우레시이데스", "tip": "처음 만났을 때"},
            {"kr": "취미는 여행이에요", "target": "趣味は旅行です", "pron": "슈미와 료코데스", "tip": "취미 소개"},
        ],
        "음식점": [
            {"kr": "메뉴 좀 볼 수 있을까요?", "target": "メニューを見せていただけますか？", "pron": "메뉴오 미세테 이타다케마스카", "tip": "메뉴 요청"},
            {"kr": "이거 추천해 주세요", "target": "おすすめは何ですか？", "pron": "오스스메와 난데스카", "tip": "추천 요청"},
            {"kr": "덜 맵게 해 주세요", "target": "辛さを控えめにしてください", "pron": "카라사오 히카에메니 시테 쿠다사이", "tip": "맛 조절 요청"},
            {"kr": "물 한 잔 주세요", "target": "お水を一杯ください", "pron": "오미즈오 잇파이 쿠다사이", "tip": "물 요청"},
            {"kr": "계산서 주세요", "target": "お会計をお願いします", "pron": "오카이케이오 오네가이시마스", "tip": "계산 요청"},
        ],
        "교통": [
            {"kr": "이 버스는 시내로 가나요?", "target": "このバスは市内に行きますか？", "pron": "코노 바스와 시나이니 이키마스카", "tip": "버스 노선 확인"},
            {"kr": "택시를 불러 주세요", "target": "タクシーを呼んでください", "pron": "타쿠시오 욘데 쿠다사이", "tip": "택시 요청"},
            {"kr": "다음 역이 어디예요?", "target": "次の駅はどこですか？", "pron": "츠기노 에키와 도코데스카", "tip": "지하철 이동"},
            {"kr": "여기서 내려 주세요", "target": "ここで降ろしてください", "pron": "코코데 오로시테 쿠다사이", "tip": "하차 요청"},
            {"kr": "얼마나 걸려요?", "target": "どのくらいかかりますか？", "pron": "도노쿠라이 카카리마스카", "tip": "소요 시간 질문"},
        ],
        "숙소": [
            {"kr": "체크인하고 싶어요", "target": "チェックインしたいです", "pron": "체크인 시타이데스", "tip": "호텔 체크인"},
            {"kr": "예약했어요", "target": "予約しています", "pron": "요야쿠시테이마스", "tip": "예약 확인"},
            {"kr": "와이파이 비밀번호가 뭐예요?", "target": "Wi-Fiのパスワードは何ですか？", "pron": "와이파이노 파스와도와 난데스카", "tip": "와이파이 문의"},
            {"kr": "수건 좀 더 주세요", "target": "タオルをもう少しください", "pron": "타오루오 모 스코시 쿠다사이", "tip": "추가 요청"},
            {"kr": "체크아웃은 몇 시예요?", "target": "チェックアウトは何時ですか？", "pron": "체크아우토와 난지데스카", "tip": "체크아웃 시간 문의"},
        ],
        "병원": [
            {"kr": "머리가 아파요", "target": "頭が痛いです", "pron": "아타마가 이타이데스", "tip": "증상 설명"},
            {"kr": "약국이 어디예요?", "target": "薬局はどこですか？", "pron": "야쿄쿠와 도코데스카", "tip": "약국 찾기"},
            {"kr": "의사를 만나고 싶어요", "target": "医者に会いたいです", "pron": "이샤니 아이타이데스", "tip": "진료 요청"},
            {"kr": "알레르기가 있어요", "target": "アレルギーがあります", "pron": "아레루기아리마스", "tip": "알레르기 설명"},
            {"kr": "응급실로 가야 하나요?", "target": "救急に行ったほうがいいですか？", "pron": "큐우큐니 잇타 호가 이이데스카", "tip": "응급 여부 확인"},
        ],
        "비즈니스": [
            {"kr": "회의는 몇 시에 시작하나요?", "target": "会議は何時に始まりますか？", "pron": "카이기와 난지니 하지마리마스카", "tip": "회의 시간 확인"},
            {"kr": "이메일로 보내 드릴게요", "target": "メールでお送りします", "pron": "메루데 오오쿠리시마스", "tip": "이메일 안내"},
            {"kr": "자료를 공유해 주세요", "target": "資料を共有してください", "pron": "시료오 쿄유시테 쿠다사이", "tip": "자료 요청"},
            {"kr": "잠시 검토할 시간이 필요해요", "target": "少し確認する時間が必要です", "pron": "스코시 카쿠닌스루 지칸가 히츠요데스", "tip": "검토 요청"},
            {"kr": "다음 주에 다시 이야기해요", "target": "来週また話しましょう", "pron": "라이슈 마타 하나시마쇼", "tip": "후속 일정"},
        ],
    },
    "zh": {
        "자기소개": [
            {"kr": "제 이름은 민지예요", "target": "我叫敏智", "pron": "워 지아오 민즈", "tip": "이름 소개"},
            {"kr": "저는 한국에서 왔어요", "target": "我来自韩国", "pron": "워 라이즈 한궈", "tip": "출신 소개"},
            {"kr": "대학교에 다니고 있어요", "target": "我在上大学", "pron": "워 짜이 샹 따쉬에", "tip": "학생 소개"},
            {"kr": "제 전공은 공학이에요", "target": "我的专业是工学", "pron": "워더 좐예 스 궁쉬에", "tip": "전공 소개"},
            {"kr": "만나서 반가워요", "target": "很高兴见到你", "pron": "헌 가오싱 지앤다오 니", "tip": "처음 만났을 때"},
            {"kr": "취미는 여행이에요", "target": "我的爱好是旅行", "pron": "워더 아이하오 스 뤼싱", "tip": "취미 소개"},
        ],
        "음식점": [
            {"kr": "메뉴 좀 볼 수 있을까요?", "target": "可以看一下菜单吗？", "pron": "커이 칸 이샤 차이단 마", "tip": "메뉴 요청"},
            {"kr": "이거 추천해 주세요", "target": "你推荐这个吗？", "pron": "니 투이지앤 저거 마", "tip": "추천 요청"},
            {"kr": "덜 맵게 해 주세요", "target": "请做得不要太辣", "pron": "칭 쭈어더 부야오 타이 라", "tip": "맛 조절 요청"},
            {"kr": "물 한 잔 주세요", "target": "请给我一杯水", "pron": "칭 게이워 이베이 쉐이", "tip": "물 요청"},
            {"kr": "계산서 주세요", "target": "请给我账单", "pron": "칭 게이워 장단", "tip": "계산 요청"},
        ],
        "교통": [
            {"kr": "이 버스는 시내로 가나요?", "target": "这辆公交车去市中心吗？", "pron": "쩌량 궁자오처 취 스중신 마", "tip": "버스 노선 확인"},
            {"kr": "택시를 불러 주세요", "target": "请帮我叫出租车", "pron": "칭 방워 지아오 추주처", "tip": "택시 요청"},
            {"kr": "다음 역이 어디예요?", "target": "下一站是哪里？", "pron": "샤이짠 스 날리", "tip": "지하철 이동"},
            {"kr": "여기서 내려 주세요", "target": "请让我在这里下车", "pron": "칭 랑워 짜이 저리 샤처", "tip": "하차 요청"},
            {"kr": "얼마나 걸려요?", "target": "要多长时间？", "pron": "야오 둬창 스지앤", "tip": "소요 시간 질문"},
        ],
        "숙소": [
            {"kr": "체크인하고 싶어요", "target": "我想办理入住", "pron": "워 샹 반리 루주", "tip": "호텔 체크인"},
            {"kr": "예약했어요", "target": "我有预订", "pron": "워 요우 위딩", "tip": "예약 확인"},
            {"kr": "와이파이 비밀번호가 뭐예요?", "target": "Wi-Fi密码是什么？", "pron": "와이파이 미마 스 션머", "tip": "와이파이 문의"},
            {"kr": "수건 좀 더 주세요", "target": "请再给我几条毛巾", "pron": "칭 짜이 게이워 지탸오 마오진", "tip": "추가 요청"},
            {"kr": "체크아웃은 몇 시예요?", "target": "退房是几点？", "pron": "투이팡 스 지디앤", "tip": "체크아웃 시간 문의"},
        ],
        "병원": [
            {"kr": "머리가 아파요", "target": "我头疼", "pron": "워 토우텅", "tip": "증상 설명"},
            {"kr": "약국이 어디예요?", "target": "药店在哪里？", "pron": "야오디앤 짜이 날리", "tip": "약국 찾기"},
            {"kr": "의사를 만나고 싶어요", "target": "我想看医生", "pron": "워 샹 칸 이성", "tip": "진료 요청"},
            {"kr": "알레르기가 있어요", "target": "我有过敏", "pron": "워 요우 궈민", "tip": "알레르기 설명"},
            {"kr": "응급실로 가야 하나요?", "target": "我需要去急诊吗？", "pron": "워 쉬야오 취 지전 마", "tip": "응급 여부 확인"},
        ],
        "비즈니스": [
            {"kr": "회의는 몇 시에 시작하나요?", "target": "会议几点开始？", "pron": "후이이 지디앤 카이스", "tip": "회의 시간 확인"},
            {"kr": "이메일로 보내 드릴게요", "target": "我会发邮件给您", "pron": "워 후이 파 요우지앤 게이 닌", "tip": "이메일 안내"},
            {"kr": "자료를 공유해 주세요", "target": "请共享资料", "pron": "칭 꽁샹 즈랴오", "tip": "자료 요청"},
            {"kr": "잠시 검토할 시간이 필요해요", "target": "我需要一点时间确认", "pron": "워 쉬야오 이디앤 스지앤 취에런", "tip": "검토 요청"},
            {"kr": "다음 주에 다시 이야기해요", "target": "我们下周再聊吧", "pron": "워먼 샤저우 짜이랴오 바", "tip": "후속 일정"},
        ],
    },
    "fr": {
        "자기소개": [
            {"kr": "제 이름은 민지예요", "target": "Je m'appelle Minji", "pron": "쥬 마펠 민지", "tip": "이름 소개"},
            {"kr": "저는 한국에서 왔어요", "target": "Je viens de Corée", "pron": "쥬 비앙 드 꼬헤", "tip": "출신 소개"},
            {"kr": "대학교에 다니고 있어요", "target": "Je vais à l'université", "pron": "쥬 베 알루니베르시떼", "tip": "학생 소개"},
            {"kr": "제 전공은 공학이에요", "target": "Ma spécialité est l'ingénierie", "pron": "마 스페시알리테 에 랭제니리", "tip": "전공 소개"},
            {"kr": "만나서 반가워요", "target": "Enchanté(e)", "pron": "앙샹떼", "tip": "처음 만났을 때"},
        ],
        "음식점": [
            {"kr": "메뉴 좀 볼 수 있을까요?", "target": "Je peux voir le menu ?", "pron": "쥬 뿌 베와흐 르 므뉴", "tip": "메뉴 요청"},
            {"kr": "이거 추천해 주세요", "target": "Qu'est-ce que vous recommandez ?", "pron": "께스크 부 흐콩망데", "tip": "추천 요청"},
            {"kr": "물 한 잔 주세요", "target": "Un verre d'eau, s'il vous plaît", "pron": "앙 베흐 도 실부플레", "tip": "물 요청"},
            {"kr": "계산서 주세요", "target": "L'addition, s'il vous plaît", "pron": "라디씨옹 실부플레", "tip": "계산 요청"},
        ],
        "교통": [
            {"kr": "이 버스는 시내로 가나요?", "target": "Ce bus va au centre-ville ?", "pron": "스 뷔스 바 오 상트르빌", "tip": "버스 노선 확인"},
            {"kr": "택시를 불러 주세요", "target": "Appelez-moi un taxi, s'il vous plaît", "pron": "아쁠레 무아 앙 딱시 실부플레", "tip": "택시 요청"},
            {"kr": "얼마나 걸려요?", "target": "Ça prend combien de temps ?", "pron": "사 프헝 꼼비앙 드 떵", "tip": "소요 시간 질문"},
        ],
        "숙소": [
            {"kr": "체크인하고 싶어요", "target": "Je voudrais m'enregistrer", "pron": "쥬 부드헤 멍헝지스트헤", "tip": "호텔 체크인"},
            {"kr": "예약했어요", "target": "J'ai une réservation", "pron": "제 윈 헤제르바시옹", "tip": "예약 확인"},
            {"kr": "체크아웃은 몇 시예요?", "target": "Le départ est à quelle heure ?", "pron": "르 데파 에타 껠르", "tip": "체크아웃 시간 문의"},
        ],
        "병원": [
            {"kr": "머리가 아파요", "target": "J'ai mal à la tête", "pron": "제 말 알라 떼뜨", "tip": "증상 설명"},
            {"kr": "약국이 어디예요?", "target": "Où est la pharmacie ?", "pron": "우 에 라 파흐마시", "tip": "약국 찾기"},
            {"kr": "의사를 만나고 싶어요", "target": "Je voudrais voir un médecin", "pron": "쥬 부드헤 부아 앙 메드생", "tip": "진료 요청"},
        ],
    },
    "de": {
        "자기소개": [
            {"kr": "제 이름은 민지예요", "target": "Ich heiße Minji", "pron": "이히 하이세 민지", "tip": "이름 소개"},
            {"kr": "저는 한국에서 왔어요", "target": "Ich komme aus Korea", "pron": "이히 코메 아우스 코레아", "tip": "출신 소개"},
            {"kr": "대학교에 다니고 있어요", "target": "Ich studiere an der Universität", "pron": "이히 슈투디레 안 데어 우니베르지테트", "tip": "학생 소개"},
            {"kr": "제 전공은 공학이에요", "target": "Mein Fach ist Ingenieurwesen", "pron": "마인 파흐 이스트 인게니외어베젠", "tip": "전공 소개"},
            {"kr": "만나서 반가워요", "target": "Freut mich", "pron": "프로이트 미히", "tip": "처음 만났을 때"},
        ],
        "음식점": [
            {"kr": "메뉴 좀 볼 수 있을까요?", "target": "Kann ich die Speisekarte sehen?", "pron": "칸 이히 디 슈파이제카르테 제엔", "tip": "메뉴 요청"},
            {"kr": "이거 추천해 주세요", "target": "Was empfehlen Sie?", "pron": "바스 엠페렌 지", "tip": "추천 요청"},
            {"kr": "물 한 잔 주세요", "target": "Ein Glas Wasser, bitte", "pron": "아인 글라스 바서 비테", "tip": "물 요청"},
            {"kr": "계산서 주세요", "target": "Die Rechnung, bitte", "pron": "디 레흐눙 비테", "tip": "계산 요청"},
        ],
        "교통": [
            {"kr": "이 버스는 시내로 가나요?", "target": "Fährt dieser Bus ins Zentrum?", "pron": "페어트 디저 부스 인스 첸트룸", "tip": "버스 노선 확인"},
            {"kr": "택시를 불러 주세요", "target": "Rufen Sie mir bitte ein Taxi", "pron": "루펜 지 미어 비테 아인 탁시", "tip": "택시 요청"},
            {"kr": "얼마나 걸려요?", "target": "Wie lange dauert es?", "pron": "비 랑에 다우어트 에스", "tip": "소요 시간 질문"},
        ],
        "숙소": [
            {"kr": "체크인하고 싶어요", "target": "Ich möchte einchecken", "pron": "이히 묘흐테 아인체켄", "tip": "호텔 체크인"},
            {"kr": "예약했어요", "target": "Ich habe reserviert", "pron": "이히 하베 레제르비어트", "tip": "예약 확인"},
            {"kr": "체크아웃은 몇 시예요?", "target": "Wann ist Check-out?", "pron": "반 이스트 체크아웃", "tip": "체크아웃 시간 문의"},
        ],
        "병원": [
            {"kr": "머리가 아파요", "target": "Ich habe Kopfschmerzen", "pron": "이히 하베 코프슈메르첸", "tip": "증상 설명"},
            {"kr": "약국이 어디예요?", "target": "Wo ist die Apotheke?", "pron": "보 이스트 디 아포테케", "tip": "약국 찾기"},
            {"kr": "의사를 만나고 싶어요", "target": "Ich möchte einen Arzt sehen", "pron": "이히 묘흐테 아이넨 아르츠트 제엔", "tip": "진료 요청"},
        ],
    },
    "it": {
        "자기소개": [
            {"kr": "제 이름은 민지예요", "target": "Mi chiamo Minji", "pron": "미 키아모 민지", "tip": "이름 소개"},
            {"kr": "저는 한국에서 왔어요", "target": "Vengo dalla Corea", "pron": "벵고 달라 코레아", "tip": "출신 소개"},
            {"kr": "대학교에 다니고 있어요", "target": "Frequento l'università", "pron": "프레퀜토 루니베르시타", "tip": "학생 소개"},
            {"kr": "제 전공은 공학이에요", "target": "La mia specializzazione è ingegneria", "pron": "라 미아 스페찰리차치오네 에 인제녜리아", "tip": "전공 소개"},
            {"kr": "만나서 반가워요", "target": "Piacere", "pron": "피아체레", "tip": "처음 만났을 때"},
        ],
        "음식점": [
            {"kr": "메뉴 좀 볼 수 있을까요?", "target": "Posso vedere il menù?", "pron": "포쏘 베데레 일 메뉴", "tip": "메뉴 요청"},
            {"kr": "이거 추천해 주세요", "target": "Che cosa mi consiglia?", "pron": "케 코자 미 콘실리아", "tip": "추천 요청"},
            {"kr": "물 한 잔 주세요", "target": "Un bicchiere d'acqua, per favore", "pron": "운 비키에레 다콰 페르 파보레", "tip": "물 요청"},
            {"kr": "계산서 주세요", "target": "Il conto, per favore", "pron": "일 콘토 페르 파보레", "tip": "계산 요청"},
        ],
        "교통": [
            {"kr": "이 버스는 시내로 가나요?", "target": "Questo autobus va in centro?", "pron": "쿠에스토 아우토부스 바 인 첸트로", "tip": "버스 노선 확인"},
            {"kr": "택시를 불러 주세요", "target": "Mi chiami un taxi, per favore", "pron": "미 키아미 운 탁시 페르 파보레", "tip": "택시 요청"},
            {"kr": "얼마나 걸려요?", "target": "Quanto tempo ci vuole?", "pron": "콴토 템포 치 부올레", "tip": "소요 시간 질문"},
        ],
        "숙소": [
            {"kr": "체크인하고 싶어요", "target": "Vorrei fare il check-in", "pron": "보레이 파레 일 체크인", "tip": "호텔 체크인"},
            {"kr": "예약했어요", "target": "Ho una prenotazione", "pron": "오 우나 프레노타치오네", "tip": "예약 확인"},
            {"kr": "체크아웃은 몇 시예요?", "target": "A che ora è il check-out?", "pron": "아 케 오라 에 일 체크아웃", "tip": "체크아웃 시간 문의"},
        ],
        "병원": [
            {"kr": "머리가 아파요", "target": "Mi fa male la testa", "pron": "미 파 말레 라 테스타", "tip": "증상 설명"},
            {"kr": "약국이 어디예요?", "target": "Dov'è la farmacia?", "pron": "도베 라 파르마치아", "tip": "약국 찾기"},
            {"kr": "의사를 만나고 싶어요", "target": "Vorrei vedere un medico", "pron": "보레이 베데레 운 메디코", "tip": "진료 요청"},
        ],
    },
}


def _apply_rich_extra_phrases() -> None:
    for lang, topics in RICH_EXTRA_PHRASES.items():
        lang_bank = FREE_PHRASES.setdefault(lang, {})
        for topic_name, extra_items in topics.items():
            current = list(lang_bank.get(topic_name, []))
            current.extend(extra_items)
            lang_bank[topic_name] = _dedupe_phrase_items(current)


_apply_rich_extra_phrases()


@dataclass
class VideoConfig:
    is_shorts: bool = True
    shadowing_pause: float = 2.2
    gap_after_kr: float = 0.8
    tail_padding: float = 1.0
    output_dir: Path = Path("outputs")
    words_per_topic: int = 5

    source_lang: str = "ko"
    target_lang: str = "es"

    use_tts: bool = True
    slow_tts: bool = False

    use_illustration_bg: bool = True
    illustration_style: str = "clean"
    visual_theme: str = "blue_card"

    bgm_path: Optional[str] = "assets/bgm.mp3"
    bgm_volume: float = 0.07
    bg_video_path: Optional[str] = "assets/bg_loop.mp4"

    brand_name: str = ""
    logo_text: str = ""
    intro_duration: float = 1.0
    title_label: str = "오늘의 표현"
    include_intro: bool = False
    show_pronunciation: bool = False

    @property
    def size(self) -> Tuple[int, int]:
        return (720, 1280) if self.is_shorts else (1280, 720)

    @property
    def kr_font_size(self) -> int:
        return 54 if self.is_shorts else 60

    @property
    def target_font_size(self) -> int:
        return 78 if self.is_shorts else 82

    @property
    def tip_font_size(self) -> int:
        return 32 if self.is_shorts else 36

    @property
    def pron_font_size(self) -> int:
        return 26 if self.is_shorts else 30


def safe_filename(text: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|]", "_", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:80] or "video"


def get_free_script(topic: str, target_lang: str, n: int) -> List[Dict[str, str]]:
    bank = FREE_PHRASES.get(target_lang, FREE_PHRASES["en"])
    topic_lower = topic.lower().strip()

    keyword_map = {
        "자기소개": ["자기소개", "소개", "첫인사", "프로필", "profile", "self", "introduce"],
        "공항": ["공항", "입국", "출국", "여권", "airport", "passport", "immigration"],
        "카페": ["카페", "커피", "음료", "디저트", "cafe", "coffee"],
        "음식점": ["음식점", "식당", "레스토랑", "메뉴", "밥", "식사", "restaurant", "food"],
        "여행": ["여행", "관광", "사진", "길", "여행지", "travel", "trip", "tour"],
        "교통": ["교통", "버스", "지하철", "택시", "기차", "이동", "transport", "bus", "taxi", "subway"],
        "숙소": ["숙소", "호텔", "체크인", "체크아웃", "와이파이", "hotel", "check-in", "check-out"],
        "학교": ["학교", "수업", "시험", "과제", "공부", "대학", "school", "class", "study"],
        "쇼핑": ["쇼핑", "옷", "할인", "사이즈", "매장", "shopping", "store"],
        "병원": ["병원", "약국", "아파", "응급", "의사", "doctor", "hospital", "pharmacy"],
        "비즈니스": ["회사", "회의", "메일", "업무", "발표", "business", "office", "meeting", "email"],
        "DM": ["dm", "디엠", "sns", "답장", "댓글", "채팅", "인스타", "message"],
    }

    selected_key = "기본"
    for key, keywords in keyword_map.items():
        if key in bank and any(k in topic_lower for k in keywords):
            selected_key = key
            break

    ordered_keys: List[str] = []
    if selected_key in bank:
        ordered_keys.append(selected_key)
    if "기본" in bank and "기본" not in ordered_keys:
        ordered_keys.append("기본")

    related_priority = {
        "자기소개": ["기본", "학교", "DM"],
        "공항": ["여행", "교통", "기본"],
        "카페": ["음식점", "쇼핑", "기본"],
        "음식점": ["카페", "여행", "기본"],
        "여행": ["교통", "숙소", "공항"],
        "교통": ["여행", "공항", "기본"],
        "숙소": ["여행", "공항", "기본"],
        "학교": ["자기소개", "기본", "비즈니스"],
        "쇼핑": ["카페", "여행", "기본"],
        "병원": ["기본", "여행"],
        "비즈니스": ["자기소개", "기본", "DM"],
        "DM": ["기본", "자기소개"],
    }
    for key in related_priority.get(selected_key, []):
        if key in bank and key not in ordered_keys:
            ordered_keys.append(key)

    for key in bank.keys():
        if key not in ordered_keys:
            ordered_keys.append(key)

    merged_items: List[Dict[str, str]] = []
    for key in ordered_keys:
        merged_items.extend(list(bank.get(key, [])))

    unique_items = _dedupe_phrase_items(merged_items)
    return unique_items[:n]

def parse_manual_items(text: str, target_lang: str) -> List[Dict[str, str]]:
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
            items.append(
                {
                    "kr": parts[0],
                    "target": parts[1],
                    "pron": pronunciation,
                    "tip": tip,
                }
            )
    return items

# --------------------------------------------------------------------------- #
# moviepy 호환
# --------------------------------------------------------------------------- #
def _with_start(clip, t: float):
    return clip.with_start(t) if hasattr(clip, "with_start") else clip.set_start(t)


def _with_duration(clip, d: float):
    return clip.with_duration(d) if hasattr(clip, "with_duration") else clip.set_duration(d)


def _with_position(clip, pos):
    return clip.with_position(pos) if hasattr(clip, "with_position") else clip.set_position(pos)


def _with_audio(clip, audio):
    return clip.with_audio(audio) if hasattr(clip, "with_audio") else clip.set_audio(audio)


def _without_audio(clip):
    if hasattr(clip, "without_audio"):
        return clip.without_audio()
    return _with_audio(clip, None)


def _subclip(clip, start: float, end: float):
    return clip.subclipped(start, end) if hasattr(clip, "subclipped") else clip.subclip(start, end)


def _resize(clip, new_size: Tuple[int, int]):
    return clip.resized(new_size) if hasattr(clip, "resized") else clip.resize(newsize=new_size)


def _scale_volume(clip, factor: float):
    if hasattr(clip, "volumex"):
        return clip.volumex(factor)
    try:
        from moviepy.audio.fx import MultiplyVolume
        return clip.with_effects([MultiplyVolume(factor)])
    except Exception:
        try:
            from moviepy.audio.fx.all import volumex
            return volumex(clip, factor)
        except Exception:
            return clip


def _crop(clip, x_center: float, y_center: float, width: int, height: int):
    try:
        from moviepy.video.fx import Crop
        return clip.with_effects([Crop(x_center=x_center, y_center=y_center, width=width, height=height)])
    except Exception:
        try:
            from moviepy.video.fx.all import crop
            return crop(clip, x_center=x_center, y_center=y_center, width=width, height=height)
        except Exception:
            return clip


def _loop_to_duration(clip, duration: float):
    try:
        from moviepy.video.fx import Loop
        return clip.with_effects([Loop(duration=duration)])
    except Exception:
        try:
            from moviepy.video.fx.all import loop
            return loop(clip, duration=duration)
        except Exception:
            reps = max(1, math.ceil(duration / max(clip.duration, 0.1)))
            looped = concatenate_videoclips([clip] * reps)
            return _subclip(looped, 0, duration)


# --------------------------------------------------------------------------- #
# 오디오
# --------------------------------------------------------------------------- #
def _audio_cache_path(text: str, lang: str, slow: bool) -> Path:
    key = hashlib.sha256(f"{text}|{lang}|{slow}".encode("utf-8")).hexdigest()[:20]
    return AUDIO_CACHE_DIR / f"{key}.mp3"


def _write_silence(path: Path, duration: float = 0.9, fps: int = 44100) -> None:
    def frame(t):
        if isinstance(t, np.ndarray):
            return np.zeros_like(t)
        return 0.0

    silent = AudioClip(frame, duration=duration, fps=fps)
    silent.write_audiofile(str(path), fps=fps, logger=None)
    silent.close()


def free_tts_to_file(text: str, lang: str, path: Path, slow: bool, use_tts: bool) -> None:
    if not use_tts:
        _write_silence(path)
        return

    AUDIO_CACHE_DIR.mkdir(exist_ok=True)
    gtts_lang = GTTS_LANG.get(lang, "en")
    cache = _audio_cache_path(text, gtts_lang, slow)

    if cache.exists():
        shutil.copy(cache, path)
        return

    try:
        tts = gTTS(text=text, lang=gtts_lang, slow=slow)
        tts.save(str(path))
        shutil.copy(path, cache)
    except Exception as e:
        log.warning("gTTS 실패, 무음으로 대체합니다: %s", e)
        _write_silence(path)


# --------------------------------------------------------------------------- #
# 폰트/텍스트 이미지
# --------------------------------------------------------------------------- #
def get_safe_font(lang: str, font_size: int):
    candidates = LANG_FONT_CANDIDATES.get(lang, LANG_FONT_CANDIDATES["en"])
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, font_size)
    return ImageFont.load_default(size=font_size)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text_to_width(text: str, font, max_width: int) -> List[str]:
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    if " " in text:
        tokens = text.split(" ")
        joiner = " "
    else:
        tokens = list(text)
        joiner = ""

    lines = []
    current = ""

    for token in tokens:
        candidate = (current + joiner + token).strip() if current else token
        width, _ = _text_size(draw, candidate, font)
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = token

    if current:
        lines.append(current)

    return lines[:4]


def make_text_image_clip(
    text: str,
    lang: str,
    font_size: int,
    color: Tuple[int, int, int, int],
    video_size: Tuple[int, int],
    max_width_ratio: float,
    duration: float,
    stroke_color: Tuple[int, int, int, int] = (0, 0, 0, 230),
    stroke_width: int = 4,
):
    font = get_safe_font(lang, font_size)
    max_width = int(video_size[0] * max_width_ratio)
    lines = wrap_text_to_width(text, font, max_width)

    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    sizes = [_text_size(draw, line, font) for line in lines]
    line_gap = int(font_size * 0.25)
    padding_x = 48
    padding_y = 24
    img_w = max([w for w, _ in sizes] + [1]) + padding_x * 2
    img_h = sum(h for _, h in sizes) + line_gap * (len(lines) - 1) + padding_y * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = padding_y
    for line, (w, h) in zip(lines, sizes):
        x = (img_w - w) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
        y += h + line_gap

    return _with_duration(ImageClip(np.array(img)), duration)


def layout_text_block(kr_clip, target_clip, tip_clip, video_size: Tuple[int, int]):
    w, h = video_size
    kr_y = int(h * 0.245)
    target_y = int(h * 0.430)
    tip_y = int(h * 0.690)
    return (
        ("center", kr_y),
        ("center", target_y),
        ("center", tip_y),
    )


def make_progress_clip(idx: int, total: int, cfg: VideoConfig, duration: float):
    theme = get_theme(cfg)
    clip = make_text_image_clip(
        text=f"{idx + 1} / {total}",
        lang="en",
        font_size=28 if cfg.is_shorts else 34,
        color=rgba(theme["dark"], 255),
        video_size=cfg.size,
        max_width_ratio=0.30,
        duration=duration,
        stroke_width=0,
    )
    x = cfg.size[0] - clip.w - int(cfg.size[0] * 0.13)
    y = int(cfg.size[1] * 0.083)
    return _with_position(clip, (x, y))


# --------------------------------------------------------------------------- #
# 무료 벡터 일러스트 배경
# --------------------------------------------------------------------------- #
PALETTES = {
    "clean": {
        "top": (248, 251, 255),
        "bottom": (238, 244, 255),
        "accent": (35, 84, 190),
        "accent2": (35, 84, 190),
        "dark": (32, 36, 44),
        "paper": (255, 255, 255),
        "glass": (255, 255, 255, 230),
        "line": (220, 228, 242),
        "soft_blue": (233, 240, 255),
    },
}
PALETTES["warm"] = PALETTES["clean"]
PALETTES["pastel"] = PALETTES["clean"]
PALETTES["night"] = PALETTES["clean"]

THEME_PRESETS = {
    "blue_card": {
        "bg_top": (248, 251, 255),
        "bg_bottom": (238, 244, 255),
        "accent": (35, 84, 190),
        "dark": (32, 36, 44),
        "muted": (74, 86, 110),
        "card": (255, 255, 255),
        "card_outline": (235, 240, 250),
        "draw_main_card": True,
        "draw_wave": True,
        "header_fill": (255, 255, 255),
        "target_on_card": True,
    },
    "plain_white": {
        "bg_top": (255, 255, 255),
        "bg_bottom": (255, 255, 255),
        "accent": (0, 0, 0),
        "dark": (0, 0, 0),
        "muted": (80, 80, 80),
        "card": (255, 255, 255),
        "card_outline": (255, 255, 255),
        "draw_main_card": False,
        "draw_wave": False,
        "header_fill": (255, 255, 255),
        "target_on_card": False,
    },
    "soft_gray": {
        "bg_top": (246, 247, 249),
        "bg_bottom": (235, 238, 243),
        "accent": (45, 45, 45),
        "dark": (28, 31, 36),
        "muted": (95, 101, 112),
        "card": (255, 255, 255),
        "card_outline": (222, 226, 235),
        "draw_main_card": True,
        "draw_wave": False,
        "header_fill": (255, 255, 255),
        "target_on_card": True,
    },
    "dark_clean": {
        "bg_top": (18, 20, 24),
        "bg_bottom": (8, 10, 13),
        "accent": (255, 255, 255),
        "dark": (255, 255, 255),
        "muted": (185, 190, 200),
        "card": (26, 29, 35),
        "card_outline": (60, 65, 75),
        "draw_main_card": True,
        "draw_wave": False,
        "header_fill": (26, 29, 35),
        "target_on_card": True,
    },
}


def get_theme(cfg):
    return THEME_PRESETS.get(getattr(cfg, "visual_theme", "blue_card"), THEME_PRESETS["blue_card"])


def rgba(rgb, alpha=255):
    return tuple(rgb) + (alpha,)


def _gradient(size: Tuple[int, int], top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> Image.Image:
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / max(h - 1, 1)
        col = [int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)]
        arr[y, :, :] = col
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _draw_soft_blob(img: Image.Image, xy, color, blur=38):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(xy, fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


def _rounded(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _scene_kind(topic: str) -> str:
    t = topic.lower()
    if any(k in t for k in ["공항", "입국", "여권", "airport", "비행"]):
        return "airport"
    if any(k in t for k in ["카페", "커피", "cafe", "coffee"]):
        return "cafe"
    if any(k in t for k in ["여행", "길", "역", "사진", "travel"]):
        return "travel"
    if any(k in t for k in ["dm", "디엠", "댓글", "답장", "인스타", "메시지"]):
        return "dm"
    if any(k in t for k in ["학교", "대학", "수업", "시험", "공부", "school"]):
        return "school"
    if any(k in t for k in ["음식", "식당", "주문", "레스토랑", "restaurant"]):
        return "food"
    return "language"


def _draw_airport(draw, w, h, p):
    # window
    _rounded(draw, (int(w*0.11), int(h*0.13), int(w*0.89), int(h*0.42)), 52, (255,255,255,80), (255,255,255,120), 3)
    draw.rectangle((int(w*0.14), int(h*0.34), int(w*0.86), int(h*0.365)), fill=(255,255,255,60))
    # plane silhouette
    cx, cy = int(w*0.58), int(h*0.235)
    draw.polygon([(cx-190, cy+18), (cx+160, cy-22), (cx+210, cy), (cx+160, cy+22)], fill=(255,255,255,210))
    draw.polygon([(cx-20, cy-5), (cx+45, cy-105), (cx+85, cy-102), (cx+45, cy+8)], fill=(255,255,255,205))
    draw.polygon([(cx-70, cy+10), (cx-10, cy+90), (cx+30, cy+86), (cx+5, cy+2)], fill=(255,255,255,190))
    # passport
    _rounded(draw, (int(w*0.12), int(h*0.66), int(w*0.35), int(h*0.84)), 28, p["dark"]+(235,), None)
    draw.ellipse((int(w*0.19), int(h*0.71), int(w*0.28), int(h*0.76)), outline=p["accent"]+(255,), width=4)
    draw.line((int(w*0.18), int(h*0.79), int(w*0.30), int(h*0.79)), fill=p["accent"]+(255,), width=5)
    # suitcase
    _rounded(draw, (int(w*0.67), int(h*0.66), int(w*0.88), int(h*0.84)), 24, p["accent2"]+(235,), None)
    draw.arc((int(w*0.72), int(h*0.61), int(w*0.83), int(h*0.70)), 180, 360, fill=p["dark"]+(230,), width=8)
    draw.line((int(w*0.72), int(h*0.70), int(w*0.83), int(h*0.70)), fill=p["dark"]+(150,), width=5)


def _draw_cafe(draw, w, h, p):
    # table
    draw.ellipse((int(w*0.08), int(h*0.73), int(w*0.92), int(h*0.92)), fill=(70, 45, 58, 110))
    # cup
    _rounded(draw, (int(w*0.32), int(h*0.57), int(w*0.64), int(h*0.77)), 44, p["paper"]+(245,), (255,255,255,190), 3)
    draw.arc((int(w*0.58), int(h*0.61), int(w*0.75), int(h*0.73)), -80, 92, fill=p["paper"]+(240,), width=16)
    draw.rectangle((int(w*0.28), int(h*0.55), int(w*0.68), int(h*0.60)), fill=p["accent"]+(245,))
    # steam
    for xoff in [-70, 0, 70]:
        x = int(w*0.48) + xoff
        draw.arc((x-26, int(h*0.45), x+45, int(h*0.56)), 90, 270, fill=(255,255,255,150), width=6)
    # pastry/card
    draw.ellipse((int(w*0.12), int(h*0.69), int(w*0.33), int(h*0.80)), fill=p["accent"]+(230,))
    _rounded(draw, (int(w*0.68), int(h*0.54), int(w*0.88), int(h*0.68)), 22, (255,255,255,105), None)
    draw.line((int(w*0.71), int(h*0.59), int(w*0.84), int(h*0.59)), fill=p["dark"]+(120,), width=5)
    draw.line((int(w*0.71), int(h*0.63), int(w*0.80), int(h*0.63)), fill=p["dark"]+(90,), width=5)


def _draw_travel(draw, w, h, p):
    # map card
    _rounded(draw, (int(w*0.10), int(h*0.18), int(w*0.90), int(h*0.52)), 42, p["paper"]+(215,), (255,255,255,180), 3)
    # route
    pts = [(int(w*0.20), int(h*0.44)), (int(w*0.35), int(h*0.29)), (int(w*0.55), int(h*0.41)), (int(w*0.77), int(h*0.26))]
    for a, b in zip(pts, pts[1:]):
        draw.line((a, b), fill=p["accent2"]+(230,), width=9)
    for x,y in pts:
        draw.ellipse((x-16,y-16,x+16,y+16), fill=p["accent"]+(255,))
    # pin
    px, py = int(w*0.77), int(h*0.26)
    draw.ellipse((px-38, py-55, px+38, py+21), fill=p["accent2"]+(255,))
    draw.polygon([(px-24, py+6), (px+24, py+6), (px, py+62)], fill=p["accent2"]+(255,))
    draw.ellipse((px-13, py-30, px+13, py-4), fill=(255,255,255,230))
    # camera
    _rounded(draw, (int(w*0.31), int(h*0.66), int(w*0.69), int(h*0.84)), 34, p["dark"]+(230,), None)
    draw.rectangle((int(w*0.39), int(h*0.62), int(w*0.52), int(h*0.67)), fill=p["dark"]+(230,))
    draw.ellipse((int(w*0.43), int(h*0.69), int(w*0.57), int(h*0.78)), fill=(255,255,255,230))
    draw.ellipse((int(w*0.46), int(h*0.71), int(w*0.54), int(h*0.76)), fill=p["accent2"]+(240,))


def _draw_dm(draw, w, h, p):
    # phone
    _rounded(draw, (int(w*0.24), int(h*0.14), int(w*0.76), int(h*0.84)), 58, p["dark"]+(245,), None)
    _rounded(draw, (int(w*0.28), int(h*0.19), int(w*0.72), int(h*0.79)), 42, (255,255,255,238), None)
    # chat bubbles
    _rounded(draw, (int(w*0.33), int(h*0.27), int(w*0.62), int(h*0.34)), 28, p["accent2"]+(230,), None)
    _rounded(draw, (int(w*0.42), int(h*0.40), int(w*0.67), int(h*0.47)), 28, p["accent"]+(235,), None)
    _rounded(draw, (int(w*0.33), int(h*0.54), int(w*0.64), int(h*0.61)), 28, p["accent2"]+(210,), None)
    _rounded(draw, (int(w*0.45), int(h*0.67), int(w*0.66), int(h*0.73)), 24, p["accent"]+(225,), None)
    for y in [0.295, 0.43, 0.57, 0.70]:
        draw.ellipse((int(w*0.36), int(h*y), int(w*0.38), int(h*y)+20), fill=(255,255,255,130))


def _draw_school(draw, w, h, p):
    # board
    _rounded(draw, (int(w*0.10), int(h*0.15), int(w*0.90), int(h*0.43)), 36, p["dark"]+(230,), (255,255,255,120), 3)
    # chalk lines
    for i, frac in enumerate([0.22, 0.28, 0.34]):
        draw.line((int(w*0.20), int(h*frac), int(w*(0.80 - i*0.08)), int(h*frac)), fill=(255,255,255,130), width=6)
    # notebook
    _rounded(draw, (int(w*0.21), int(h*0.60), int(w*0.67), int(h*0.84)), 24, p["paper"]+(240,), None)
    for x in range(int(w*0.26), int(w*0.64), int(w*0.055)):
        draw.line((x, int(h*0.61), x, int(h*0.83)), fill=(120,130,160,60), width=2)
    for y in range(int(h*0.65), int(h*0.82), int(h*0.035)):
        draw.line((int(w*0.25), y, int(w*0.64), y), fill=(120,130,160,65), width=2)
    # pencil
    draw.polygon([(int(w*0.66), int(h*0.63)), (int(w*0.86), int(h*0.75)), (int(w*0.82), int(h*0.80)), (int(w*0.62), int(h*0.68))], fill=p["accent"]+(245,))
    draw.polygon([(int(w*0.86), int(h*0.75)), (int(w*0.91), int(h*0.78)), (int(w*0.82), int(h*0.80))], fill=p["dark"]+(230,))


def _draw_food(draw, w, h, p):
    # plate
    draw.ellipse((int(w*0.18), int(h*0.60), int(w*0.82), int(h*0.86)), fill=(255,255,255,235))
    draw.ellipse((int(w*0.27), int(h*0.65), int(w*0.73), int(h*0.81)), fill=(255,236,206,235))
    # food blobs
    draw.ellipse((int(w*0.36), int(h*0.66), int(w*0.56), int(h*0.77)), fill=p["accent2"]+(230,))
    draw.ellipse((int(w*0.49), int(h*0.65), int(w*0.66), int(h*0.76)), fill=p["accent"]+(230,))
    draw.ellipse((int(w*0.29), int(h*0.69), int(w*0.43), int(h*0.78)), fill=(110, 190, 120, 230))
    # fork/spoon
    draw.line((int(w*0.13), int(h*0.55), int(w*0.24), int(h*0.86)), fill=(255,255,255,210), width=8)
    draw.line((int(w*0.87), int(h*0.55), int(w*0.76), int(h*0.86)), fill=(255,255,255,210), width=8)


def _draw_language(draw, w, h, p):
    cards = [
        (0.14, 0.18, 0.40, 0.36, "A"),
        (0.58, 0.21, 0.84, 0.39, "あ"),
        (0.18, 0.64, 0.44, 0.82, "¡"),
        (0.56, 0.62, 0.82, 0.80, "你"),
    ]
    for x1,y1,x2,y2,txt in cards:
        _rounded(draw, (int(w*x1), int(h*y1), int(w*x2), int(h*y2)), 34, p["paper"]+(180,), (255,255,255,160), 3)
        try:
            font = get_safe_font("ja" if txt in ["あ", "你"] else "en", int(h*0.07))
            bbox = draw.textbbox((0,0), txt, font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            draw.text((int(w*(x1+x2)/2 - tw/2), int(h*(y1+y2)/2 - th/2)), txt, font=font, fill=p["dark"]+(235,))
        except Exception:
            pass


def make_illustration_background(topic: str, cfg: VideoConfig, idx: int, total: int) -> Image.Image:
    w, h = cfg.size
    theme = get_theme(cfg)
    img = _gradient((w, h), theme["bg_top"], theme["bg_bottom"])

    if getattr(cfg, "visual_theme", "blue_card") in ["blue_card", "soft_gray"]:
        _draw_soft_blob(
            img,
            (int(w * 0.03), int(h * 0.16), int(w * 0.97), int(h * 0.80)),
            (255, 255, 255, 120),
            blur=90,
        )

    draw = ImageDraw.Draw(img, "RGBA")

    if theme.get("draw_main_card", True):
        card_x1 = int(w * 0.075)
        card_x2 = int(w * 0.925)
        card_y1 = int(h * 0.345)
        card_y2 = int(h * 0.675)

        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow, "RGBA")
        shadow_alpha = 24 if getattr(cfg, "visual_theme", "blue_card") != "dark_clean" else 65
        sd.rounded_rectangle(
            (card_x1, card_y1 + int(h * 0.010), card_x2, card_y2 + int(h * 0.010)),
            radius=int(w * 0.055),
            fill=(0, 0, 0, shadow_alpha),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        img.alpha_composite(shadow)

        draw = ImageDraw.Draw(img, "RGBA")
        draw.rounded_rectangle(
            (card_x1, card_y1, card_x2, card_y2),
            radius=int(w * 0.055),
            fill=rgba(theme["card"], 246),
            outline=rgba(theme["card_outline"], 180),
            width=2,
        )

    if theme.get("draw_wave", False):
        accent = rgba(theme["accent"], 255)
        wave = [
            (0, h),
            (0, int(h * 0.965)),
            (int(w * 0.20), int(h * 0.940)),
            (int(w * 0.38), int(h * 0.915)),
            (int(w * 0.58), int(h * 0.920)),
            (int(w * 0.78), int(h * 0.895)),
            (w, int(h * 0.780)),
            (w, h),
        ]
        draw.polygon(wave, fill=accent)

    return img


# --------------------------------------------------------------------------- #
# 브랜딩 오버레이 / 인트로
# --------------------------------------------------------------------------- #
def make_brand_badge_clip(cfg: VideoConfig, duration: float):
    w, h = cfg.size
    card_w = int(w * 0.17)
    card_h = int(h * 0.06)
    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle((0, 0, card_w-1, card_h-1), radius=int(card_h*0.34), fill=(255,255,255,230), outline=(255,255,255,250), width=2)
    logo_font = get_safe_font("en", int(card_h * 0.42))
    name_font = get_safe_font("en", int(card_h * 0.25))
    draw.ellipse((int(card_w*0.08), int(card_h*0.18), int(card_w*0.34), int(card_h*0.82)), fill=(122,162,255,255))
    lbox = draw.textbbox((0, 0), cfg.logo_text, font=logo_font)
    lw = lbox[2] - lbox[0]
    lh = lbox[3] - lbox[1]
    draw.text((int(card_w*0.21 - lw/2), int(card_h*0.50 - lh/2)), cfg.logo_text, font=logo_font, fill=(255,255,255,255))
    draw.text((int(card_w*0.39), int(card_h*0.23)), cfg.brand_name, font=name_font, fill=(40,55,88,255))
    draw.text((int(card_w*0.39), int(card_h*0.50)), "LANGUAGE SHORTS", font=name_font, fill=(90,105,135,255))
    clip = _with_duration(ImageClip(np.array(img)), duration)
    return _with_position(clip, (int(w*0.055), int(h*0.04)))


def make_title_box_clip(topic: str, cfg: VideoConfig, duration: float, intro: bool = False):
    w, h = cfg.size
    theme = get_theme(cfg)

    box_w = int(w * (0.86 if cfg.is_shorts else 0.58))
    box_h = int(h * (0.105 if not intro else 0.13))
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))

    if getattr(cfg, "visual_theme", "blue_card") != "plain_white":
        shadow = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow, "RGBA")
        shadow_alpha = 18 if getattr(cfg, "visual_theme", "blue_card") != "dark_clean" else 55
        sd.rounded_rectangle(
            (2, 4, box_w - 2, box_h - 2),
            radius=int(box_h * 0.38),
            fill=(0, 0, 0, shadow_alpha),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        img.alpha_composite(shadow)

    draw = ImageDraw.Draw(img, "RGBA")
    fill_alpha = 236 if getattr(cfg, "visual_theme", "blue_card") != "plain_white" else 0
    outline_alpha = 210 if getattr(cfg, "visual_theme", "blue_card") != "plain_white" else 0

    draw.rounded_rectangle(
        (0, 0, box_w - 1, box_h - 1),
        radius=int(box_h * 0.38),
        fill=rgba(theme["header_fill"], fill_alpha),
        outline=rgba(theme["card_outline"], outline_alpha),
        width=2,
    )

    accent = rgba(theme["accent"], 255)
    dark = rgba(theme["dark"], 255)
    muted = rgba(theme["muted"], 255)

    draw.rounded_rectangle(
        (int(box_w * 0.045), int(box_h * 0.22), int(box_w * 0.057), int(box_h * 0.78)),
        radius=5,
        fill=accent,
    )

    label_font = get_safe_font("ko", int(box_h * 0.20))
    title_font = get_safe_font("ko", int(box_h * 0.25))
    topic_text = topic if len(topic) <= 18 else topic[:18] + "…"

    draw.text((int(box_w * 0.10), int(box_h * 0.22)), cfg.title_label, font=label_font, fill=muted)
    draw.text((int(box_w * 0.10), int(box_h * 0.50)), topic_text, font=title_font, fill=dark)

    clip = _with_duration(ImageClip(np.array(img)), duration)
    x = int((w - box_w) / 2)
    y = int(h * (0.055 if not intro else 0.38))
    return _with_position(clip, (x, y))


def make_intro_caption_clip(cfg: VideoConfig, duration: float):
    theme = get_theme(cfg)
    text = f"{LANG_DISPLAY_NAMES.get(cfg.target_lang, cfg.target_lang)} 표현을 시작해볼게요"
    clip = make_text_image_clip(
        text=text,
        lang="ko",
        font_size=30 if cfg.is_shorts else 34,
        color=rgba(theme["dark"], 255),
        video_size=cfg.size,
        max_width_ratio=0.82,
        duration=duration,
        stroke_width=0,
    )
    return _with_position(clip, ("center", int(cfg.size[1] * 0.53)))


def make_intro_clip(topic: str, cfg: VideoConfig, bg_source=None):
    duration = max(0.8, float(cfg.intro_duration))
    bg = build_background_layer(bg_source, cfg, duration, topic=topic, idx=-1, total=1)
    title = make_title_box_clip(topic, cfg, duration, intro=True)
    caption = make_intro_caption_clip(cfg, duration)
    intro = CompositeVideoClip([bg, title, caption], size=cfg.size)
    return _with_duration(intro, duration)


# --------------------------------------------------------------------------- #
# 배경
# --------------------------------------------------------------------------- #
def _cover_resize_crop(clip, target_size: Tuple[int, int]):
    tw, th = target_size
    scale = max(tw / clip.w, th / clip.h)
    clip = _resize(clip, (int(clip.w * scale) + 2, int(clip.h * scale) + 2))
    return _crop(clip, x_center=clip.w / 2, y_center=clip.h / 2, width=tw, height=th)


def load_bg_source(cfg: VideoConfig):
    if not cfg.bg_video_path:
        return None

    path = Path(cfg.bg_video_path)
    if not path.exists():
        return None

    try:
        clip = VideoFileClip(str(path))
        clip = _without_audio(clip)
        return _cover_resize_crop(clip, cfg.size)
    except Exception as e:
        log.warning("배경 영상 실패: %s", e)
        return None


def build_background_layer(bg_source, cfg: VideoConfig, duration: float, topic: str, idx: int, total: int):
    if bg_source is not None:
        try:
            clip = bg_source
            if clip.duration < duration:
                clip = _loop_to_duration(clip, duration)
            clip = _subclip(clip, 0, duration)
            return _with_duration(clip, duration)
        except Exception:
            pass

    if cfg.use_illustration_bg:
        img = make_illustration_background(topic, cfg, idx, total)
        return _with_duration(ImageClip(np.array(img)), duration)

    return ColorClip(size=cfg.size, color=(26, 26, 30), duration=duration)


def add_background_music(final_video, cfg: VideoConfig):
    if not cfg.bgm_path:
        return final_video

    path = Path(cfg.bgm_path)
    if not path.exists():
        return final_video

    try:
        bgm = AudioFileClip(str(path))
        duration = final_video.duration
        if bgm.duration < duration:
            loops = math.ceil(duration / max(bgm.duration, 0.1))
            bgm = concatenate_audioclips([bgm] * loops)
        bgm = _subclip(bgm, 0, duration)
        bgm = _with_start(_scale_volume(bgm, cfg.bgm_volume), 0)

        mixed = CompositeAudioClip([final_video.audio, bgm]) if final_video.audio else CompositeAudioClip([bgm])
        mixed = _with_duration(mixed, duration)
        return _with_audio(final_video, mixed)
    except Exception as e:
        log.warning("BGM 실패: %s", e)
        return final_video


# --------------------------------------------------------------------------- #
# 생성
# --------------------------------------------------------------------------- #
def build_word_segment(
    topic: str,
    item: Dict[str, str],
    cfg: VideoConfig,
    tmp_dir: Path,
    idx: int,
    total: int,
    bg_source=None,
):
    kr_path = tmp_dir / f"kr_{idx}.mp3"
    target_path = tmp_dir / f"target_{idx}.mp3"

    free_tts_to_file(item["kr"], cfg.source_lang, kr_path, cfg.slow_tts, cfg.use_tts)
    free_tts_to_file(item["target"], cfg.target_lang, target_path, cfg.slow_tts, cfg.use_tts)

    audio_kr = AudioFileClip(str(kr_path))
    audio_target = AudioFileClip(str(target_path))

    start_target1 = audio_kr.duration + cfg.gap_after_kr
    start_target2 = start_target1 + audio_target.duration + cfg.shadowing_pause
    total_duration = start_target2 + audio_target.duration + cfg.tail_padding

    combined_audio = CompositeAudioClip(
        [
            _with_start(audio_kr, 0),
            _with_start(audio_target, start_target1),
            _with_start(audio_target, start_target2),
        ]
    )
    combined_audio = _with_duration(combined_audio, total_duration)

    bg = build_background_layer(bg_source, cfg, total_duration, topic=topic, idx=idx, total=total)
    theme = get_theme(cfg)
    target_color = theme["accent"] if theme.get("target_on_card", True) else theme["dark"]

    kr_clip = make_text_image_clip(
        item["kr"],
        lang=cfg.source_lang,
        font_size=cfg.kr_font_size,
        color=rgba(theme["dark"], 255),
        video_size=cfg.size,
        max_width_ratio=0.82,
        duration=total_duration,
        stroke_width=0,
    )

    target_clip = make_text_image_clip(
        item["target"],
        lang=cfg.target_lang,
        font_size=cfg.target_font_size,
        color=rgba(target_color, 255),
        video_size=cfg.size,
        max_width_ratio=0.78,
        duration=total_duration,
        stroke_width=0,
    )

    pronunciation_text = (item.get("pron") or "").strip()
    show_pron = bool(cfg.show_pronunciation and pronunciation_text)
    pron_clip = None
    if show_pron:
        pron_clip = make_text_image_clip(
            pronunciation_text,
            lang="ko",
            font_size=cfg.pron_font_size,
            color=rgba(theme["muted"], 255),
            video_size=cfg.size,
            max_width_ratio=0.76,
            duration=total_duration,
            stroke_width=0,
        )

    tip_clip = make_text_image_clip(
        item.get("tip") or "소리 내서 따라 해보세요",
        lang=cfg.source_lang,
        font_size=cfg.tip_font_size,
        color=rgba(theme["dark"], 255),
        video_size=cfg.size,
        max_width_ratio=0.78,
        duration=total_duration,
        stroke_width=0,
    )

    _, h = cfg.size
    kr_pos = ("center", int(h * 0.245))
    target_pos = ("center", int(h * 0.410))
    if show_pron:
        pron_pos = ("center", int(h * 0.585))
        tip_pos = ("center", int(h * 0.705))
    else:
        pron_pos = None
        tip_pos = ("center", int(h * 0.690))

    kr_in = 0.08
    target_in = 0.20
    pron_in = 0.28
    tip_in = 0.34
    kr_clip = _with_start(_with_duration(_with_position(kr_clip, kr_pos), max(0.1, total_duration - kr_in)), kr_in)
    target_clip = _with_start(_with_duration(_with_position(target_clip, target_pos), max(0.1, total_duration - target_in)), target_in)
    layers = [
        bg,
        make_title_box_clip(topic, cfg, total_duration, intro=False),
        make_progress_clip(idx, total, cfg, total_duration),
        kr_clip,
        target_clip,
    ]

    if show_pron and pron_clip is not None and pron_pos is not None:
        pron_clip = _with_start(_with_duration(_with_position(pron_clip, pron_pos), max(0.1, total_duration - pron_in)), pron_in)
        layers.append(pron_clip)

    tip_clip = _with_start(_with_duration(_with_position(tip_clip, tip_pos), max(0.1, total_duration - tip_in)), tip_in)
    layers.append(tip_clip)

    segment = CompositeVideoClip(layers, size=cfg.size)
    segment = _with_audio(segment, combined_audio)

    return segment, [audio_kr, audio_target]

def create_study_video(
    topic: str,
    items: List[Dict[str, str]],
    cfg: VideoConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    def progress(message: str):
        log.info(message)
        if progress_callback:
            progress_callback(message)

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(exist_ok=True)

    suffix = "shorts" if cfg.is_shorts else "long"
    intro_tag = "intro" if cfg.include_intro else "nointro"
    pron_tag = "pron" if cfg.show_pronunciation else "nopron"
    output_path = cfg.output_dir / f"{safe_filename(topic)}_{cfg.target_lang}_{intro_tag}_{pron_tag}_{suffix}.mp4"

    bg_source = load_bg_source(cfg)
    video_clips = []
    audio_handles = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        total = len(items)

        if cfg.include_intro:
            progress("1/3 인트로 카드 생성 중")
            intro_clip = make_intro_clip(topic, cfg, bg_source=bg_source)
            video_clips.append(intro_clip)

        for idx, item in enumerate(items):
            progress(f"1/3 음성/자막/일러스트 생성 중: {idx + 1}/{total} - {item['kr']} → {item['target']}")
            segment, handles = build_word_segment(topic, item, cfg, tmp_dir, idx, total, bg_source=bg_source)
            video_clips.append(segment)
            audio_handles.extend(handles)

        if not video_clips:
            raise RuntimeError("생성 가능한 영상 클립이 없습니다.")

        progress("2/3 클립 병합 및 BGM 처리 중")
        final_video = concatenate_videoclips(video_clips, method="compose")
        final_video = add_background_music(final_video, cfg)

        progress("3/3 mp4 렌더링 중")
        final_video.write_videofile(
            str(output_path),
            fps=20,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=2,
            logger=None,
        )

        final_video.close()

        for clip in video_clips:
            try:
                clip.close()
            except Exception:
                pass
        for handle in audio_handles:
            try:
                handle.close()
            except Exception:
                pass

    if bg_source is not None:
        try:
            bg_source.close()
        except Exception:
            pass

    progress(f"완료: {output_path}")
    return output_path
