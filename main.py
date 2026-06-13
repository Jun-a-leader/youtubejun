import streamlit as st
from googleapiclient.discovery import build
import re
import pandas as pd
from konlpy.tag import Okt
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import urllib.request
import os

# 1. 한글 폰트 다운로드 함수 (워드클라우드 깨짐 방지)
@st.cache_resource
def download_font():
    font_url = "https://github.com/naver/nanum-fonts/raw/main/成熟/NanumGothic.ttf"
    font_path = "NanumGothic.ttf"
    if not os.path.exists(font_path):
        with st.spinner("한글 폰트를 다운로드 중입니다..."):
            urllib.request.urlretrieve(font_url, font_path)
    return font_path

# 2. 유튜브 비디오 ID 추출 함수
def extract_video_id(url):
    pattern = r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

# 3. 유튜브 댓글 수집 함수
def get_youtube_comments(api_key, video_id, max_results=100):
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        comments = []
        
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            textFormat="plainText"
        )
        
        while request and len(comments) < max_results:
            response = request.execute()
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)
            
            # 다음 페이지가 있고, 목표 개수보다 적게 모았으면 계속 수집
            if 'nextPageToken' in response and len(comments) < max_results:
                request = youtube.commentThreads().list_next(request, response)
            else:
                break
                
        return comments
    except Exception as e:
        st.error(True)
        st.error(f"API 호출 중 오류 발생: {e}")
        return []

# 4. 한글 형태소 분석 및 명사 추출 함수
def process_korean_text(comments):
    okt = Okt()
    all_text = " ".join(comments)
    # 한글과 공백만 남기기
    clean_text = re.sub(r'[^가-힣\s]', '', all_text)
    
    # 명사만 추출 (2글자 이상만)
    nouns = okt.nouns(clean_text)
    words = [word for word in nouns if len(word) > 1]
    
    # 간단한 불용어(제외할 단어) 처리
    stopwords = ['유튜브', '영상', '이거', '진짜', '너무', '완전', '보고', '보는데', '댓글']
    words = [word for word in words if word not in stopwords]
    
    return " ".join(words)

# --- 스트림릿 UI 시작 ---
st.set_page_config(page_title="유튜브 댓글 심층 분석기", layout="wide", page_icon="📊")

st.title("📊 유튜브 댓글 심층 분석기")
st.markdown("유튜브 링크를 입력하면 댓글을 수집하여 핵심 키워드(워드클라우드)와 긍정/부정 분위기를 분석합니다.")

# 사이드바 - 설정
st.sidebar.header("🔑 설정")
api_key = st.sidebar.text_input("YouTube API Key를 입력하세요", type="password")
max_comments = st.sidebar.slider("수집할 댓글 개수", min_value=50, max_value=500, value=100, step=50)

st.sidebar.markdown("---")
st.sidebar.info("💡 **팁:** API 키는 구글 클라우드 콘솔에서 발급받을 수 있습니다.")

# 메인 화면 - 입력창
video_url = st.text_input("분석할 유튜브 동영상 링크를 입력하세요:", placeholder="https://www.youtube.com/watch?v=...")

if st.button("🚀 댓글 분석 시작", use_container_width=True):
    if not api_key:
        st.warning("사이드바에 YouTube API Key를 입력해주세요.")
    elif not video_url:
        st.warning("유튜브 동영상 링크를 입력해주세요.")
    else:
        video_id = extract_video_id(video_url)
        
        if not video_id:
            st.error("올바른 유튜브 URL 형식이 아닙니다. 다시 확인해주세요.")
        else:
            with st.spinner("📥 유튜브에서 댓글을 수집하는 중..."):
                comments = get_youtube_comments(api_key, video_id, max_comments)
            
            if comments:
                st.success(f"총 {len(comments)}개의 댓글을 성공적으로 수집했습니다!")
                
                # 데이터프레임 변환 및 전처리
                df = pd.DataFrame(comments, columns=["댓글 내용"])
                
                # 한글 폰트 로드
                font_path = download_font()
                
                # 형태소 분석
                with st.spinner("🧠 한글 형태소 분석 및 데이터 가공 중..."):
                    processed_text = process_korean_text(comments)
                
                # 레이아웃 나누기 (2단 구성)
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("☁️ 핵심 키워드 워드클라우드")
                    if processed_text.strip():
                        # 워드클라우드 생성
                        wc = WordCloud(
                            font_path=font_path,
                            background_color="white",
                            width=800,
                            height=600,
                            max_words=100,
                            colormap="crimson"
                        ).generate(processed_text)
                        
                        # 시각화
                        fig, ax = plt.subplots(figsize=(10, 8))
                        ax.imshow(wc, interpolation="bilinear")
                        ax.axis("off")
                        st.pyplot(fig)
                    else:
                        st.info("분석할 수 있는 유의미한 한글 명사 단어가 부족합니다.")
                
                with col2:
                    st.subheader("💬 수집된 원본 댓글 예시 (최신순)")
                    st.dataframe(df, use_container_width=True, height=450)
                    
                # 간단한 텍스트 기반 감정 분석 (미니 기능)
                st.markdown("---")
                st.subheader("📈 간단 감정 트렌드 분석")
                
                # 규칙 기반 간단 긍/부정 단어 체크
                pos_words = ['좋다', '최고', '감사', '유익', '재밌', '대박', '짱', '지렸다', '최고다', '재미', '감동']
                neg_words = ['노잼', '실망', '별로', '노답', '최악', '아쉽', '불편', '삭제', '거름', '지루']
                
                pos_count = sum(1 for c in comments if any(w in c for w in pos_words))
                neg_count = sum(1 for c in comments if any(w in c for w in neg_words))
                neutral_count = len(comments) - (pos_count + neg_count)
                
                # 감정 지표 시각화
                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.metric("😊 긍정적인 반응의 댓글", f"{pos_count}개", f"{pos_count/len(comments)*100:.1f}%")
                m_col2.metric("🤬 부정적인 반응의 댓글", f"{neg_count}개", f"-{neg_count/len(comments)*100:.1f}%")
                m_col3.metric("😐 기타/중립 댓글", f"{neutral_count}개", f"{neutral_count/len(comments)*100:.1f}%")
