import os
import shutil
import json
import asyncio
import requests
import urllib.parse
import streamlit as st
import edge_tts
import google.generativeai as genai
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

# ---------------------------------------------------------
# 🔑 API 키 고정 설정
# ---------------------------------------------------------
GEMINI_API_KEY = "AIzaSyClTMO8YUNLPKFPpJP9XHzeO0mxaaW2WOw"
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 기본 설정 (모바일 최적화)
st.set_page_config(page_title="승석Bot 🤖 - 전문 지식 스토리보드", page_icon="🤖", layout="centered")

st.title("🤖 승석Bot: 전문 지식 스토리보드 스튜디오")
st.markdown("대본을 입력하면 AI가 **타임라인 별 씬(Scene)을 분할**하고 이미지를 매칭하여, 고품질 전문 지식 영상을 완성해 냅니다!")

# 폴더 초기화 (임시 저장소)
TEMP_DIR = "temp_channel"
IMG_DIR = os.path.join(TEMP_DIR, "images")
AUDIO_DIR = os.path.join(TEMP_DIR, "audios")
VIDEO_FILE = os.path.join(TEMP_DIR, "final_video.mp4")

def init_folders():
    for d in [TEMP_DIR, IMG_DIR, AUDIO_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

init_folders()

# 사이드바 설정 영역
with st.sidebar:
    st.markdown(
        """
        <h2><a href="/" style="text-decoration: none; color: inherit; display: block; margin-bottom: 20px;">🤖 승석Bot 홈</a></h2>
        """, 
        unsafe_allow_html=True
    )
    st.header("⚙️ 공간 관리")
    st.markdown("진행 중인 모든 스토리보드와 임시 파일을 초기화합니다.")
        
    if st.button("새로 시작(초기화)"):
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        init_folders()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("초기화 완료! 화면을 새로고침 해주세요.")

# 상태 관리 (Session State)
if "step" not in st.session_state:
    st.session_state.step = 1
if "timeline_data" not in st.session_state:
    st.session_state.timeline_data = []

# ==========================================
# 1단계: 타임라인 생성 (Script to Timeline)
# ==========================================
if st.session_state.step == 1:
    st.subheader("📝 1단계: 대본 입력 및 타임라인 분석")
    script_text = st.text_area("영상에 들어갈 대본을 작성해주세요.", height=200, 
                               placeholder="현대 사회에서 인공지능이 왜 중요한지 알아보겠습니다...", max_chars=10000)
    
    if st.button("🔍 타임라인 분석 시작", type="primary", use_container_width=True):
        if not script_text.strip():
            st.error("대본을 입력해주세요.")
        else:
            with st.spinner("🧠 파싱 중... (대본을 의미 단위 씬으로 나누는 중)"):
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt_req = f"""
                    다음 영상 대본을 4~8개의 의미 있는 씬(장면)으로 분할해줘.
                    응답은 반드시 아래와 같은 JSON 배열 (Array of Objects) 구문으로만 반환해. 다른 설명이나 마크다운 백틱(```)은 절대 붙이지 마.

                    [
                      {{"scene_id": 1, "text": "첫 번째 씬의 대본 문장입니다.", "prompt": "English prompt describing the first scene, highly detailed, professional, cinematic lighting, 4k"}},
                      {{"scene_id": 2, "text": "두 번째 씬의 대본 문장입니다.", "prompt": "English prompt describing the second scene, ..."}}
                    ]

                    대본:
                    {script_text}
                    """
                    response = model.generate_content(prompt_req)
                    
                    # JSON 파싱 준비 (가끔 백틱이나 추가 설명이 올 경우를 대비)
                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    parsed_data = json.loads(raw_text)
                    
                    # 이미지 경로 초기화
                    for item in parsed_data:
                        item["image_path"] = None
                        
                    st.session_state.timeline_data = parsed_data
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"타임라인 분석 중 오류가 발생했습니다: {e}")
                    st.error("대본을 조금 변경하거나 다시 시도해주세요.")

# ==========================================
# 2단계: 이미지 매칭 및 스토리보드 (Storyboard View)
# ==========================================
elif st.session_state.step == 2:
    st.subheader("🎞️ 2단계: 이미지 매칭 및 스토리보드")
    st.markdown("각 씬(Scene)별로 텍스트 분할이 완료되었습니다. **'이미지 자동 생성'** 버튼을 차례로 눌러 씬마다 알맞은 이미지를 렌더링하세요.")
    
    all_images_ready = True
    
    for idx, scene in enumerate(st.session_state.timeline_data):
        st.write(f"### 🎬 Scene {scene['scene_id']}")
        st.info(f"📜 대본: {scene['text']}")
        st.caption(f"✨ 프롬프트: {scene['prompt']}")
        
        col_img, col_btn = st.columns([1, 1])
        
        with col_img:
            if scene.get("image_path") and os.path.exists(scene["image_path"]):
                st.image(scene["image_path"], use_column_width=True)
            else:
                st.markdown(
                    "<div style='height:200px; display:flex; align-items:center; justify-content:center; background-color:#333; color:white; border-radius:10px;'>이미지 없음</div>", 
                    unsafe_allow_html=True
                )
                all_images_ready = False
                
        with col_btn:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("🎨 이미지 자동 생성", key=f"btn_gen_{idx}"):
                with st.spinner(f"Scene {scene['scene_id']} 이미지 렌더링 중..."):
                    safe_prompt = urllib.parse.quote(scene['prompt'])
                    # Pollinations AI를 활용한 안정적 무료 생성
                    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1080&height=1920&nologo=true"
                    r = requests.get(url)
                    if r.status_code == 200:
                        img_path = os.path.join(IMG_DIR, f"scene_{scene['scene_id']}.png")
                        with open(img_path, "wb") as f:
                            f.write(r.content)
                        st.session_state.timeline_data[idx]["image_path"] = img_path
                        st.rerun()
                    else:
                        st.error("이미지 생성 서버 지연. 다시 눌러주세요.")
                        
        st.divider()

    if all_images_ready:
        st.success("모든 씬의 이미지 준비가 완료되었습니다! 최종 렌더링을 시작하세요.")
        if st.button("🎬 최종 영상 제작 시작", type="primary", use_container_width=True):
            st.session_state.step = 3
            st.rerun()
    else:
        st.warning("모든 씬의 이미지를 생성해야 최종 영상 제작이 가능합니다.")
        
    if st.button("⬅️ 대본 다시 쓰기 (1단계로)"):
        st.session_state.step = 1
        st.rerun()

# ==========================================
# 3단계: 최종 렌더링 (Click to Video)
# ==========================================
elif st.session_state.step == 3:
    st.subheader("🚀 3단계: 최종 렌더링")
    
    with st.status("🎬 비디오 렌더링 파이프라인 작동 중...", expanded=True) as status:
        try:
            timeline_data = st.session_state.timeline_data
            clips = []
            
            # 1. TTS 생성 및 각 씬별 영상 클립 조립 (시간 매칭)
            st.write("1️⃣ 각 씬별로 Edge TTS 음성 생성 및 오디오 클립 조합 중...")
            
            async def generate_scene_audio(text, out_path):
                communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
                await communicate.save(out_path)
            
            # 동시 비동기 처리를 위한 리스트
            async def generate_all_audios():
                tasks = []
                for i, scene in enumerate(timeline_data):
                    out_path = os.path.join(AUDIO_DIR, f"audio_{i}.mp3")
                    tasks.append(generate_scene_audio(scene['text'], out_path))
                await asyncio.gather(*tasks)
                
            asyncio.run(generate_all_audios())
            
            st.write("2️⃣ 무빙 효과 및 자막(맑은 고딕), 크로스페이드 합성 적용 중...")
            
            for i, scene in enumerate(timeline_data):
                img_path = scene['image_path']
                audio_path = os.path.join(AUDIO_DIR, f"audio_{i}.mp3")
                
                audio_clip = AudioFileClip(audio_path)
                
                crossfade_duration = 0.5 # 자연스러운 트랜지션
                # 마지막 씬이 아니면 오디오 길이 + 크로스페이드 여유시간 확보
                clip_duration = audio_clip.duration
                if i < len(timeline_data) - 1:
                    clip_duration += crossfade_duration
                    
                orig_clip = ImageClip(img_path)
                w, h = orig_clip.w, orig_clip.h
                
                # 줌인 (Ken Burns)
                zoom_speed = 0.05 / clip_duration 
                zoomed_clip = orig_clip.resize(lambda t: 1 + (zoom_speed * t))
                animated_clip = CompositeVideoClip([zoomed_clip.set_position("center")], size=(w, h)).set_duration(clip_duration)
                
                # 트랜지션
                if i > 0:
                    animated_clip = animated_clip.crossfadein(crossfade_duration)
                
                # 해당 씬 대본 자막 (맑은 고딕 고정)
                try:
                    txt_clip = TextClip(scene['text'], fontsize=45, color='white', 
                                      font='Malgun-Gothic', stroke_color='black', stroke_width=2, method='caption', size=(w - 100, None))
                    txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(clip_duration)
                    animated_clip = CompositeVideoClip([animated_clip, txt_clip])
                except Exception as e:
                    if i == 0:
                        st.warning(f"자막 렌더링 경고 (ImageMagick 확인 요망): {e}")

                # 영상 클립에 오디오 장착
                animated_clip = animated_clip.set_audio(audio_clip)
                clips.append(animated_clip)
                
            st.write("3️⃣ 최종 MP4 파일 인코딩 중... (시간이 소요될 수 있습니다)")
            # 각 씬별 클립을 결합
            final_video = concatenate_videoclips(clips, padding=-crossfade_duration, method="compose")
            final_video.write_videofile(VIDEO_FILE, fps=24, codec="libx264", audio_codec="aac", logger=None)
            
            status.update(label="✨ 스토리보드 기반 전문 지식 영상이 완성되었습니다!", state="complete", expanded=False)
            
        except Exception as e:
            status.update(label="❌ 렌더링 중 오류가 발생했습니다.", state="error", expanded=True)
            st.error(f"오류 상세: {e}")
            st.stop()
            
    # 결과물 출력 (비디오 플레이어 및 다운로드)
    if os.path.exists(VIDEO_FILE):
        st.success("영상 렌더링에 성공했습니다! 결과물을 확인해 주세요.")
        
        st.video(VIDEO_FILE)
            
        with open(VIDEO_FILE, "rb") as file:
            st.download_button(
                label="📥 롱폼 비디오 다운로드 (.mp4)",
                data=file,
                file_name="youtube_longform_video.mp4",
                mime="video/mp4",
                type="primary",
                use_container_width=True
            )
            
    if st.button("🔄 처음부터 다시 시작"):
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
