import os
import shutil
import json
import asyncio
import requests
import urllib.parse
import streamlit as st
import edge_tts
import google.generativeai as genai
from PIL import Image
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

# ---------------------------------------------------------
# 🔑 API 키 고정 설정
# ---------------------------------------------------------
# 🔑 API 설정: 코드에 적지 않고 웹페이지 화면(UI)에서 받기!
# ---------------------------------------------------------

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
    
    st.header("🔑 구글 API 설정")
    st.markdown("API 키 보호를 위해 화면에서 직접 입력받습니다. (저장되지 않습니다)")
    user_api_key = st.text_input("Gemini API Key 입력:", type="password", placeholder="AIzaSy...")
    
    st.divider()
    
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
    st.subheader("🎨 1단계: 영상 스타일 선택")
    st.markdown("영상 전체의 분위기와 퀄리티를 결정할 아트 스타일을 선택해 주세요.")
    
    style_options = {
        "디즈니 3D": {
            "desc": "귀여운 캐릭터, 풍부한 색감 🏰", 
            "prompt": "Disney/Pixar 3D animation style, cute character, vibrant colors",
            "img": "https://picsum.photos/seed/disney/400/300"
        },
        "실사풍 3D": {
            "desc": "고유의 3D 질감, 영화 같은 조명 🎬", 
            "prompt": "High-end realistic 3D, cinematic lighting",
            "img": "https://picsum.photos/seed/realistic/400/300"
        },
        "일본 지브리풍": {
            "desc": "지브리풍 감성, 부드러운 수채화 배경 🌸", 
            "prompt": "Studio Ghibli style, soft watercolor",
            "img": "https://picsum.photos/seed/ghibli/400/300"
        },
        "2D 인포그래픽": {
            "desc": "전문적인 벡터 일러스트, 깔끔한 플랫 디자인 📊", 
            "prompt": "Clean modern vector infographic",
            "img": "https://picsum.photos/seed/info/400/300"
        },
        "사이버펑크": {
            "desc": "사이버펑크 미학, 네온 조명 🌆", 
            "prompt": "Cyberpunk aesthetic, neon lights",
            "img": "https://picsum.photos/seed/cyber/400/300"
        },
        "클레이 애니메이션": {
            "desc": "스톱 모션 클레이메이션 찰흙 느낌 🍡", 
            "prompt": "Stop-motion claymation style",
            "img": "https://picsum.photos/seed/clay/400/300"
        },
        "수채화 일러스트": {
            "desc": "아름다운 수채화 페인팅 🖌️", 
            "prompt": "Beautiful watercolor painting",
            "img": "https://picsum.photos/seed/water/400/300"
        },
        "레트로 코믹북": {
            "desc": "빈티지 코믹북 스타일, 하프톤 💥", 
            "prompt": "Vintage comic book style, halftone",
            "img": "https://picsum.photos/seed/comic/400/300"
        },
        "팝아트": {
            "desc": "강렬하고 생기 넘치는 팝아트 🎨", 
            "prompt": "Vibrant Pop Art style",
            "img": "https://picsum.photos/seed/popart/400/300"
        },
        "미니멀리즘": {
            "desc": "미니멀리스트 플랫 디자인, 솔리드 컬러 🧊", 
            "prompt": "Minimalist flat design, solid colors",
            "img": "https://picsum.photos/seed/minimal/400/300"
        },
        "3D 로우폴리": {
            "desc": "3D 로우 폴리 아이소메트릭 아트 💎", 
            "prompt": "3D low poly isometric art",
            "img": "https://picsum.photos/seed/lowpoly/400/300"
        },
        "픽셀 아트": {
            "desc": "디테일한 16비트 픽셀 아트 👾", 
            "prompt": "Detailed 16-bit pixel art",
            "img": "https://picsum.photos/seed/pixel/400/300"
        },
        "연필 스케치": {
            "desc": "거칠고 디테일한 연필 스케치 ✏️", 
            "prompt": "Detailed rough pencil sketch",
            "img": "https://picsum.photos/seed/sketch/400/300"
        },
        "오일 페인팅": {
            "desc": "클래식 오일 페인팅 스타일 🖼️", 
            "prompt": "Classic oil painting style",
            "img": "https://picsum.photos/seed/oil/400/300"
        },
        "흑백 누아르": {
            "desc": "흑백 누아르 시네마틱 🎞️", 
            "prompt": "Black and white noir cinematic",
            "img": "https://picsum.photos/seed/noir/400/300"
        },
        "디즈니 2D 클래식": {
            "desc": "클래식 2D 디즈니 애니, 셀 셰이딩 🕰️", 
            "prompt": "Classic 2D Disney animation style, vintage cel shading, flat vibrant colors",
            "img": "https://picsum.photos/seed/classic2d/400/300"
        }
    }
    
    # 기본 스타일 지정
    if "video_style" not in st.session_state:
        st.session_state.video_style = "2D 인포그래픽"
        
    st.info(f"🎨 현재 적용된 스타일: **{st.session_state.video_style}**")
    
    # 4열(Columns) 그리드 레이아웃 적용
    keys = list(style_options.keys())
    
    # 4개씩 짝지어서 row 구성
    for i in range(0, len(keys), 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < len(keys):
                style_name = keys[i+j]
                with cols[j]:
                    st.image(style_options[style_name]["img"], use_column_width=True)
                    if st.button(f"✨ {style_name}", key=f"btn_style_{i+j}", use_container_width=True):
                        st.session_state.video_style = style_name
                        st.rerun()
                        
    selected_style_prompt = style_options[st.session_state.video_style]["prompt"]
    
    st.divider()
    
    st.subheader("📝 2단계: 대본 입력 및 주인공 설정")
    script_text = st.text_area("영상에 들어갈 대본을 작성해주세요.", height=200, 
                               placeholder="현대 사회에서 인공지능이 왜 중요한지 알아보겠습니다...", max_chars=10000)
                               
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 👤 주인공 캐릭터 고정 설정 (선택사항)")
        st.markdown("특정 인물을 영상 내내 주인공으로 등장시키고 싶다면 아래에 참조 이미지를 올려주세요.")
        char_image_file = st.file_uploader(
            "👇 주인공 캐릭터 이미지를 이곳에 드래그 앤 드롭하거나 클릭해서 찾아보기", 
            type=['png', 'jpg', 'jpeg']
        )
        if char_image_file:
            st.success("✨ 주인공 이미지가 성공적으로 등록되었습니다. 모든 씬에 이 캐릭터 외형이 고정됩니다!")
            st.image(char_image_file, width=200, caption="설정된 주인공 캐릭터")
    
    if st.button("🔍 타임라인 분석 시작", type="primary", use_container_width=True):
        if not user_api_key.strip():
            st.error("⚠️ 좌측 사이드바에 구글 Gemini API 키를 먼저 입력해주세요!")
        elif not script_text.strip():
            st.error("대본을 입력해주세요.")
        else:
            with st.spinner("🧠 파싱 중... (대본을 의미 단위 씬으로 나누는 중)"):
                try:
                    # 입력받은 API 키로 실시간 설정 구성
                    genai.configure(api_key=user_api_key.strip())
                    
                    # 최신 멀티모달 모델 통합 사용 (텍스트, 이미지 모두 1.5-flash로 일원화)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    char_desc = ""
                    if char_image_file:
                        with st.spinner("✨ 캐릭터 특징 분석 중..."):
                            img = Image.open(char_image_file)
                            char_prompt = "Describe the physical appearance of this character (hair color, clothing, face, age, prominent features) in a very short and clear English sentence. Start with 'A character with...'"
                            # 리스트 형태로 텍스트와 이미지를 한 번에 전달하는 최신 문법
                            char_res = model.generate_content([char_prompt, img])
                            char_desc = char_res.text.strip()
                            st.session_state.character_description = char_desc
                            st.session_state.character_image = char_image_file.getvalue()
                    else:
                        st.session_state.character_description = ""
                        st.session_state.character_image = None
                        
                    prompt_req = f"""
                    다음 영상 대본을 4~8개의 의미 있는 씬(장면)으로 분할해줘.
                    응답은 반드시 아래와 같은 JSON 배열 (Array of Objects) 구문으로만 반환해. 다른 설명이나 마크다운 백틱(```)은 절대 붙이지 마.

                    [
                      {{"scene_id": 1, "text": "첫 번째 씬의 대본 문장입니다.", "prompt": "English prompt describing the first scene, highly detailed"}},
                      {{"scene_id": 2, "text": "두 번째 씬의 대본 문장입니다.", "prompt": "English prompt describing the second scene, ..."}}
                    ]

                    대본:
                    {script_text}
                    """
                    response = model.generate_content(prompt_req)
                    
                    # JSON 파싱 준비
                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    parsed_data = json.loads(raw_text)
                    
                    # 기본 프롬프트 강화 및 이미지 경로 초기화 (스타일 + 캐릭터 고정 + 씬 상황)
                    for item in parsed_data:
                        base_p = item["prompt"]
                        # [스타일 지시] + [캐릭터 고정 묘사] + [해당 씬 배경 및 상황] 순서로 자연스럽게 결합 (문자 충돌 방지)
                        merged_prompt = f"{selected_style_prompt}. "
                        if char_desc:
                            merged_prompt += f"{char_desc}. In this scene: {base_p}. no text, 4k resolution"
                        else:
                            merged_prompt += f"Scene description: {base_p}. no text, 4k resolution"
                            
                        item["prompt"] = merged_prompt
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
    st.subheader("🎞️ 스토리보드 이미지 매칭")
    
    # 상단 락(Lock) 정보 - 스타일 및 캐릭터 노출
    st.info("💡 설정된 주인공 캐릭터와 스타일이 모든 씬에 일관되게 반영됩니다.")
    with st.container(border=True):
        st.markdown(f"**🎨 적용된 영상 스타일:** `{st.session_state.get('video_style', '기본값')}`")
        if st.session_state.get("character_image") and st.session_state.get("character_description"):
            char_cols = st.columns([1, 2])
            with char_cols[0]:
                st.image(st.session_state.character_image, use_column_width=True)
            with char_cols[1]:
                st.markdown("**설정된 주인공 (AI 추출 외형):**")
                st.caption(f"{st.session_state.character_description}")
            
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
