import streamlit as st
from googleapiclient.discovery import build
import re
import pandas as pd
from kiwipiepy import Kiwi
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import urllib.request
import os

# 1. 구글 저장소에서 한글 폰트 안전하게 다운로드
@st.cache_resource
def download_font():
    font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
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
            
            if 'nextPageToken' in response and len(comments) < max_results:
                request = youtube.commentThreads().list_next(request, response)
            else:
                break
                
        return comments
    except Exception as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return []

# 4. 한글(명사) + 영어(단어) 통합 처리 함수
def process_multilingual_text(comments):
    kiwi = Kiwi()
    combined_words = []
    
    # 불용어 설정 (한글/영어 공통)
    stopwords = {
        '유튜브', '영상', '이거', '진짜', '너무', '완전', '보고', '보는데', '댓글', '생각', '하나',
        'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'to', 'for', 'of', 'in', 'on', 'at',
        'this', 'that', 'it', 'you', 'i', 'my', 'me', 'your', 'with', 'so', 'just', 'like', 'not', 'no'
    }
    
    for comment in comments:
        # 1. 영어 단어 추출 (소문자 변환 후 2글자 이상만)
        english_words = re.findall(r'[a-zA-Z]+', comment)
        for word in english_words:
            w_lower = word.lower()
            if len(w_lower) > 1 and w_lower not in stopwords:
                combined_words.append(w_lower)
                
        # 2. 한글 명사 추출 (2글자 이상만)
        clean_korean = re.sub(r'[^가-힣\s]', '', comment)
        if clean_korean.strip():
            tokens = kiwi.tokenize(clean_korean)
            for token in tokens:
                if token.tag in ['NNG', 'NNP'] and len(token.form) > 1 and token.form not in stopwords:
                    combined_words.append(token.form)
                    
    return " ".join(combined_words)

# --- 스트림릿 UI 시작 ---
st.set_page_config(page_title="유튜브 댓글 심층 분석기", layout="wide", page_icon="📊")

st.title("📊 유튜브 댓글 심층 분석기")
st.markdown("유튜브 링크를 입력하면 댓글을 수집하여 다국어 워드클라우드와 긍정/부정 분위기를 분석합니다.            사용 전 Youtube API키를 확인해주세요. 키가 없다면 이용이 불가합니다. 키 확인은 다음 주소에서 가능합니다 https://console.cloud.google.com/")

# 사이드바 - 설정
st.sidebar.header("🔑 설정")
api_key = st.sidebar.text_input("YouTube API Key를 입력하세요. 입력 완료 후 Enter키로 적용합니다", type="password")


max_comments = st.sidebar.slider("분석할 댓글 개수", min_value=100, max_value=50000, value=300, step=100)

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
                
                df = pd.DataFrame(comments, columns=["댓글 내용"])
                font_path = download_font()
                
                with st.spinner("🧠 한글/영어 텍스트 분석 및 가공 중..."):
                    processed_text = process_multilingual_text(comments)
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("☁️ 핵심 키워드 워드클라우드")
                    if processed_text.strip():
                        wc = WordCloud(
                            font_path=font_path,
                            background_color="white",
                            width=800,
                            height=600,
                            max_words=100,
                            colormap="plasma"
                        ).generate(processed_text)
                        
                        fig, ax = plt.subplots(figsize=(10, 8))
                        ax.imshow(wc, interpolation="bilinear")
                        ax.axis("off")
                        st.pyplot(fig)
                    else:
                        st.info("분석할 수 있는 유의미한 단어가 부족합니다.")
                
                with col2:
                    st.subheader("💬 수집된 원본 댓글 예시 (최신순)")
                    st.dataframe(df, use_container_width=True, height=450)
                    
                st.markdown("---")
                st.subheader("📈 간단 감정 트렌드 분석")
                
                # 다국어 감정 단어 체크 리스트
                pos_words = ['좋다', '최고', '감사', '유익', '재밌', '대박', '짱', '지렸다', '재미', '감동', 'good', 'best', 'love', 'awesome', 'amazing', 'great', 'cool']
                neg_words = ['노잼', '실망', '별로', '노답', '최악', '아쉽', '불편', '삭제', '거름', '지루', 'bad', 'worst', 'boring', 'disappoint', 'hate', 'waste']
                
                pos_count = sum(1 for c in comments if any(w in c.lower() for w in pos_words))
                neg_count = sum(1 for c in comments if any(w in c.lower() for w in neg_words))
                neutral_count = len(comments) - (pos_count + neg_count)
                
                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.metric("😊 긍정적인 반응의 댓글", f"{pos_count}개", f"{pos_count/len(comments)*100:.1f}%")
                m_col2.metric("🤬 부정적인 반응의 댓글", f"{neg_count}개", f"-{neg_count/len(comments)*100:.1f}%")
                m_col3.metric("😐 기타/중립 댓글", f"{neutral_count}개", f"{neutral_count/len(comments)*100:.1f}%")
