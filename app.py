import streamlit as st
import streamlit.components.v1 as components
import cv2
import yt_dlp
import numpy as np
import os
import tempfile
import sys
import shutil
import logging
from math import ceil

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Slide Snatcher", layout="wide")
st.title("📸 YouTube Slide Snatcher (Segment Mode)")
st.markdown("Step 1: Select **Segments** or **Chapters**. Step 2: Download & Scan.")

# Check for FFmpeg
if not shutil.which('ffmpeg'):
    st.info("ℹ️ FFmpeg not detected. Using **Video Only** mode. Downloads will snap to the nearest keyframe.")

# --- SESSION STATE INITIALIZATION ---
if 'video_info' not in st.session_state:
    st.session_state['video_info'] = None
if 'url_input' not in st.session_state:
    st.session_state['url_input'] = ""
if 'captured_images' not in st.session_state:
    st.session_state['captured_images'] = []
if 'ready_segment' not in st.session_state:
    st.session_state['ready_segment'] = None 

# --------------------------------------------------------------------------
# PROXY & AUTHENTICATION SETUP (FROM SECRETS)
# --------------------------------------------------------------------------
proxy_url = None
if "proxy_url" in st.secrets:
    proxy_url = st.secrets["proxy_url"]
else:
    st.warning("⚠️ No 'proxy_url' found in secrets! Downloads might fail.")

@st.cache_resource
def setup_cookies_file():
    if "cookies" not in st.secrets:
        st.warning("⚠️ No 'cookies' found in secrets! YouTube will treat this as a bot.")
        return None
    try:
        cookies_content = st.secrets["cookies"]
        fp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
        fp.write(cookies_content)
        fp.close()
        return fp.name
    except Exception as e:
        st.error(f"Error setting up cookies: {e}")
        return None

cookies_path = setup_cookies_file()

# 2. SIDEBAR SETTINGS
with st.sidebar:
    st.header("⚙️ Settings")
    st.subheader("🔍 Detection Settings")
    sensitivity = st.slider("Color Sensitivity", min_value=10, max_value=100, value=35, help="Higher = less sensitive to small color changes")
    strictness = st.slider("Strictness (%)", min_value=0.1, max_value=100.0, value=1.0, step=0.1, help="Percentage of screen that must change to trigger a capture")
    st.divider()
    st.info("💡 **Speed Tip:** Adjust jump intervals")
    min_skip = st.slider("Min Jump (Seconds)", 1, 5, 2)
    max_skip = st.slider("Max Jump (Seconds)", 5, 30, 10)

# --- LOGGING ---
class MyLogger:
    def __init__(self): self.logs = []
    def debug(self, msg): pass
    def info(self, msg): self.logs.append(f"[INFO] {msg}")
    def warning(self, msg): self.logs.append(f"[WARN] {msg}")
    def error(self, msg): self.logs.append(f"[ERROR] {msg}")

# --- HELPERS: METADATA ---
def get_video_info(youtube_url, cookies_file=None, proxy=None):
    logger = MyLogger()
    # ADDED USER AGENT TO BYPASS BOT CHECK
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'logger': logger, 
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    if cookies_file: ydl_opts['cookiefile'] = cookies_file
    if proxy: ydl_opts['proxy'] = proxy
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(youtube_url, download=False), None
    except Exception as e:
        return None, f"{str(e)}\n\nLogs:\n" + "\n".join(logger.logs)

def create_pdf(image_buffers):
    if not image_buffers: return None
    output_path = os.path.join(tempfile.gettempdir(), "lecture_slides.pdf")
    pil_images = []
    from PIL import Image
    for buf in image_buffers:
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None: continue
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_images.append(Image.fromarray(img_rgb))
    if pil_images:
        pil_images[0].save(output_path, "PDF", resolution=100.0, save_all=True, append_images=pil_images[1:])
        return output_path
    return None

def fmt_time(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60); 
    if hours > 0: return f"{int(hours)}h {int(mins)}m {int(secs)}s"
    return f"{int(mins)}m {int(secs)}s"

# 4. MAIN APP INTERFACE
url = st.text_input("1. Enter YouTube URL:", value=st.session_state['url_input'], placeholder="https://www.youtube.com/watch?v=...")

if st.button("Fetch Info 🔎"):
    if not url:
        st.error("Please enter a URL.")
    else:
        with st.spinner("Fetching video info..."):
            info, error_msg = get_video_info(url, cookies_file=cookies_path, proxy=proxy_url)
            if info:
                st.session_state['video_info'] = info
                st.session_state['url_input'] = url 
                st.session_state['ready_segment'] = None
                st.session_state['captured_images'] = []
                st.rerun() 
            else:
                st.error(f"❌ Could not find video. Error details:\n\n{error_msg}")

if st.session_state['video_info'] and url == st.session_state['url_input']:
    info = st.session_state['video_info']
    
    st.divider()
    col_a, col_b = st.columns([1, 3])
    with col_a:
        if info.get('thumbnail'): st.image(info['thumbnail'], use_container_width=True)
    with col_b:
        st.subheader(info.get('title', 'Unknown'))
        duration = info.get('duration', 0)
        st.write(f"**Duration:** {fmt_time(duration)}")
        st.write(f"**Uploader:** {info.get('uploader', 'Unknown')}")
    
    # --- QUALITY SELECTION ---
    st.subheader("2. Select Quality (Video Only)")
    formats = info.get('formats', [])
    unique_heights = set()
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('height'): 
            unique_heights.add(f['height'])
    sorted_heights = sorted(unique_heights, reverse=True)
    
    quality_options = {}
    for h in sorted_heights: 
        quality_options[f"{h}p"] = f"bestvideo[height<={h}]"
    quality_options["Best Available"] = "bestvideo"
    
    selected_q_label = st.selectbox("Choose quality:", list(quality_options.keys()))

    # --- TIME RANGE SELECTION ---
    st.subheader("3. Select Segments to Download")
    
    chapters = info.get('chapters')
    use_chapters = False
    
    if chapters:
        use_chapters = st.checkbox(f"Use YouTube Chapters ({len(chapters)} found)", value=True)
    
    start_val = 0
    end_val = duration
    
    if use_chapters and chapters:
        chapter_names = [f"{i+1}. {c['title']} ({fmt_time(c['start_time'])})" for i, c in enumerate(chapters)]
        start_chapter_idx, end_chapter_idx = st.select_slider(
            "Select Chapter Range",
            options=range(len(chapters)),
            value=(0, len(chapters)-1),
            format_func=lambda i: chapter_names[i]
        )
        start_val = chapters[start_chapter_idx]['start_time']
        end_val = chapters[end_chapter_idx]['end_time']
        st.info(f"📍 Selected: **{chapters[start_chapter_idx]['title']}** to **{chapters[end_chapter_idx]['title']}**")
        
    else:
        st.markdown("YouTube stores videos in small data chunks. Select which continuous segments you want to download.")
        col_seg_1, col_seg_2 = st.columns([1, 3])
        with col_seg_1:
            seg_len = st.selectbox("Segment Size", [10, 30, 60], index=0, format_func=lambda x: f"{x} Seconds")
        
        total_segments = ceil(duration / seg_len)
        
        with col_seg_2:
            sel_range = st.slider(
                f"Select Segment Range (Total {total_segments})", 
                1, total_segments, (1, min(5, total_segments))
            )
            
        start_val = (sel_range[0] - 1) * seg_len
        end_val = sel_range[1] * seg_len
        if end_val > duration: end_val = duration
        
        st.info(f"⏱️ Downloading **Segments {sel_range[0]} - {sel_range[1]}** (Time: {fmt_time(start_val)} to {fmt_time(end_val)})")
    
    # --- ACTION BUTTONS ---
    col_btn_1, col_btn_2 = st.columns(2)
    start_scan_btn = col_btn_1.button("Download & Scan 🚀", type="primary")
    process_dl_btn = col_btn_2.button("Download Segment Only 📥")

    format_str = quality_options[selected_q_label]
    def download_range_func(info_dict, ydl):
        return [{'start_time': start_val, 'end_time': end_val}]

    # --- DOWNLOAD ONLY LOGIC ---
    if process_dl_btn:
        st.session_state['captured_images'] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'proxy': proxy_url,
                'cookiefile': cookies_path,
                'quiet': True,
                'no_warnings': True,
                'download_ranges': download_range_func,
                # ADDED USER AGENT HERE TOO
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }
            try:
                with st.spinner("Downloading video segment..."):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                
                files = os.listdir(tmp_dir)
                if files:
                    file_name = files[0]
                    file_path = os.path.join(tmp_dir, file_name)
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                    
                    st.session_state['ready_segment'] = {
                        'name': file_name,
                        'data': file_bytes
                    }
                    st.success("✅ Segment Ready! Click download below.")
                else:
                    st.error("Download failed (file not found).")
            except Exception as e:
                st.error(f"Download Error: {e}")

    # --- DOWNLOAD & SCAN LOGIC ---
    if start_scan_btn:
        st.session_state['ready_segment'] = None
        st.session_state['captured_images'] = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    p = d.get('_percent_str', '0%').replace('%', '')
                    if p and p != 'N/A':
                        progress_bar.progress(min(float(p) / 100, 1.0))
                    status_text.text(f"Downloading: {d.get('_percent_str')} - ETA: {d.get('_eta_str')}")
                except: pass
            elif d['status'] == 'finished':
                progress_bar.progress(1.0)
                status_text.text("Download complete. Starting Scan...")

        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'proxy': proxy_url,
                'cookiefile': cookies_path,
                'quiet': True,
                'no_warnings': True,
                'download_ranges': download_range_func,
                # ADDED USER AGENT HERE TOO
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }

            try:
                with st.spinner("Downloading video segments to server..."):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                
                files = os.listdir(tmp_dir)
                if files:
                    file_name = files[0]
                    file_path = os.path.join(tmp_dir, file_name)
                    
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                    
                    st.session_state['ready_segment'] = {
                        'name': file_name,
                        'data': file_bytes
                    }

                    status_text.info(f"📂 Scanning local file: {file_name}")
                    
                    cap = cv2.VideoCapture(file_path)
                    if not cap.isOpened():
                        st.error("Error opening downloaded video file.")
                    else:
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        if fps <= 0: fps = 30
                        
                        last_frame_data = None
                        current_frame_pos = 0 
                        total_frames_in_file = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        end_frame_pos = total_frames_in_file
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        
                        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        process_w = 640
                        process_h = int(process_w * (orig_h / orig_w)) if orig_w > 0 else 360
                        total_pixel_count = process_w * process_h
                        motion_threshold_score = int(total_pixel_count * (strictness / 100) * 255)
                        jump_small = int(fps * min_skip)
                        jump_large = int(fps * max_skip)
                        
                        st.divider()
                        st.subheader("Scanning Results")
                        
                        while current_frame_pos < end_frame_pos:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_pos)
                            ret, frame = cap.read()
                            if not ret: break
                            
                            if total_frames_in_file > 0:
                                progress_bar.progress(min(current_frame_pos / total_frames_in_file, 1.0))
                                
                            small_frame = cv2.resize(frame, (process_w, process_h))
                            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                            gray = cv2.GaussianBlur(gray, (21, 21), 0)
                            
                            found_new_slide = False
                            if last_frame_data is None:
                                found_new_slide = True
                                last_frame_data = gray
                            else:
                                diff = cv2.absdiff(last_frame_data, gray)
                                _, thresh = cv2.threshold(diff, sensitivity, 255, cv2.THRESH_BINARY)
                                if np.sum(thresh) > motion_threshold_score:
                                    found_new_slide = True
                                    last_frame_data = gray
                            
                            if found_new_slide:
                                retval, buffer = cv2.imencode('.jpg', frame)
                                if retval:
                                    st.session_state['captured_images'].append(buffer)
                                
                                current_file_time = current_frame_pos / fps
                                actual_video_time = current_file_time + start_val
                                time_str = fmt_time(actual_video_time)
                                
                                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                st.image(img_rgb, caption=f"Found at {time_str}", channels="RGB")
                                
                                current_frame_pos += jump_large 
                            else:
                                current_frame_pos += jump_small
                        
                        cap.release()
                        progress_bar.empty()
                        status_text.success(f"✅ Scanning Complete!")

                else:
                    st.error("Download finished but file not found on server.")
            except Exception as e:
                st.error(f"Process failed: {e}")

    # --- DISPLAY DOWNLOADS (Persistent) ---
    if len(st.session_state.get('captured_images', [])) > 0 or st.session_state['ready_segment']:
        st.divider()
        st.subheader("📥 Downloads")
        col_res_1, col_res_2 = st.columns(2)
        
        with col_res_1:
            if st.session_state['ready_segment']:
                st.download_button(
                    label=f"💾 Save Video Segment '{st.session_state['ready_segment']['name']}'",
                    data=st.session_state['ready_segment']['data'],
                    file_name=st.session_state['ready_segment']['name'],
                    mime="application/octet-stream",
                    key="dl_vid_btn_final"
                )
            else:
                st.info("No video segment ready.")

        with col_res_2:
            if len(st.session_state.get('captured_images', [])) > 0:
                pdf_path = create_pdf(st.session_state['captured_images'])
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button("📄 Save Slides as PDF", f.read(), "slides.pdf", "application/pdf", key="dl_pdf_btn")
            elif start_scan_btn:
                st.info("No slides detected in this segment.")
