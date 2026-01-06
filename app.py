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
from PIL import Image

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Slide Snatcher", layout="wide")
st.title("📸 YouTube Slide Snatcher (Download & Scan Mode)")
st.markdown("Step 1: Download video segment to server. Step 2: Auto-scan for slides.")

# Check for FFmpeg
if not shutil.which('ffmpeg'):
    st.warning("⚠️ FFmpeg is not installed. Video processing might fail.")

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
# PROXY & AUTHENTICATION SETUP
# --------------------------------------------------------------------------
# Load Proxy from Secrets
proxy_url = None
if "proxy_url" in st.secrets:
    proxy_url = st.secrets["proxy_url"]
elif "PROXY_URL" in st.secrets:
    proxy_url = st.secrets["PROXY_URL"]
else:
    # Optional warning, or just silent
    pass

# Load Cookies from Secrets (Default)
secret_cookies_path = None
if "cookies" in st.secrets:
    try:
        cookies_content = st.secrets["cookies"]
        fp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
        fp.write(cookies_content)
        fp.close()
        secret_cookies_path = fp.name
    except Exception as e:
        st.error(f"Error setting up secret cookies: {e}")

# 2. SIDEBAR SETTINGS
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.subheader("🍪 Authentication")
    st.markdown("Upload `cookies.txt` to bypass age restrictions. (Overrides secrets)")
    uploaded_cookies = st.file_uploader("Upload cookies.txt", type=['txt'])
    
    # LOGIC: Use Uploaded if exists, else use Secret, else None
    cookies_path = secret_cookies_path
    if uploaded_cookies:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='wb') as fp:
                fp.write(uploaded_cookies.getvalue())
                cookies_path = fp.name
            st.success("✅ Uploaded cookies loaded")
        except Exception as e:
            st.error(f"Error loading uploaded cookies: {e}")
    elif secret_cookies_path:
        st.info("ℹ️ Using cookies from secrets")

    st.divider()
    
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

# --- HELPERS: METADATA & PDF ---
def get_video_info(youtube_url, cookies_file=None, proxy=None):
    logger = MyLogger()
    # Updated: Prioritize iOS client which is more stable on servers
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'logger': logger, 
        'nocheckcertificate': True,
        'extractor_args': {'youtube': {'player_client': ['ios', 'web']}}
    }
    
    if cookies_file: 
        ydl_opts['cookiefile'] = cookies_file
        # Android is good if cookies are present
        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'ios', 'web']}}

    if proxy: 
        ydl_opts['proxy'] = proxy
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(youtube_url, download=False), None
    except Exception as e:
        return None, f"{str(e)}\n\nLogs:\n" + "\n".join(logger.logs)

def create_pdf(image_buffers):
    if not image_buffers: return None
    output_path = os.path.join(tempfile.gettempdir(), f"slides_{os.urandom(4).hex()}.pdf")
    pil_images = []
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
        st.caption(f"**Duration:** {fmt_time(info.get('duration', 0))} | **Uploader:** {info.get('uploader', 'Unknown')}")
    
    # --- QUALITY SELECTION ---
    st.subheader("2. Select Quality")
    formats = info.get('formats', [])
    unique_heights = set()
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('height'): 
            unique_heights.add(f['height'])
    sorted_heights = sorted(unique_heights, reverse=True)
    
    quality_options = {}
    for h in sorted_heights: 
        quality_options[f"{h}p"] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
    quality_options["Best Available"] = "bestvideo+bestaudio/best"
    
    selected_q_label = st.selectbox("Choose quality:", list(quality_options.keys()))

    # --- TIME RANGE SELECTION ---
    st.subheader("3. Select Time Range to Scan")
    duration = info.get('duration', 100)
    start_val, end_val = st.slider("Drag sliders to select scan range:", min_value=0, max_value=duration, value=(0, min(duration, 300)), format="mm:ss")
    st.info(f"⏱️ Will download and scan only from **{fmt_time(start_val)}** to **{fmt_time(end_val)}**")
    
    col_btn1, col_btn2 = st.columns(2)
    start_scan = col_btn1.button("Download & Scan 🚀", type="primary")
    dl_video_only = col_btn2.button("Download Clip Only 📥")

    if start_scan or dl_video_only:
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
                status_text.text("Download complete. Processing...")

        format_str = quality_options[selected_q_label]
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'proxy': proxy_url,
                'cookiefile': cookies_path,
                'quiet': True,
                'no_warnings': True,
                'download_ranges': lambda _, __: [{'start_time': start_val, 'end_time': end_val}],
                'force_keyframes_at_cuts': True,
                # Set extractor args to be robust
                'extractor_args': {'youtube': {'player_client': ['ios', 'web']}},
            }
            
            if cookies_path:
                ydl_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'ios', 'web']}}

            try:
                # 1. DOWNLOAD (Retry Logic)
                with st.spinner("Downloading video segment to server..."):
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                    except Exception as e:
                        status_text.warning("Specific quality failed. Retrying with 'Best Available' format...")
                        # Fallback to simple format and ios client
                        ydl_opts['format'] = 'best'
                        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['ios', 'web']}}
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                
                # Check file
                files = os.listdir(tmp_dir)
                if files:
                    file_name = files[0]
                    file_path = os.path.join(tmp_dir, file_name)
                    
                    # Store video for download if requested
                    if dl_video_only:
                        with open(file_path, "rb") as f:
                             st.session_state['ready_segment'] = {'name': file_name, 'data': f.read()}
                        status_text.success("✅ Video segment ready below!")
                    
                    # 2. SCANNING LOGIC
                    elif start_scan:
                        status_text.info(f"📂 Scanning local file: {file_name}")
                        cap = cv2.VideoCapture(file_path)
                        if not cap.isOpened():
                            st.error("Error opening downloaded video file.")
                        else:
                            fps = cap.get(cv2.CAP_PROP_FPS) or 30
                            total_frames_in_file = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                            
                            # Scan loop
                            current_frame_pos = 0
                            end_frame_pos = total_frames_in_file
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            
                            orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            process_w = 640
                            process_h = int(process_w * (orig_h / orig_w)) if orig_w > 0 else 360
                            
                            motion_threshold_score = int((process_w * process_h) * (strictness / 100) * 255)
                            jump_small = int(fps * min_skip)
                            jump_large = int(fps * max_skip)
                            
                            last_frame_data = None
                            
                            st.divider()
                            st.subheader("Results")
                            
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
                                        
                                        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                        st.image(img_rgb, caption=f"Slide #{len(st.session_state['captured_images'])} at {fmt_time(actual_video_time)}", channels="RGB")
                                        current_frame_pos += jump_large 
                                else:
                                    current_frame_pos += jump_small
                            
                            cap.release()
                            progress_bar.empty()
                            status_text.success(f"✅ Scanning Complete! Found {len(st.session_state['captured_images'])} slides.")

                else:
                    st.error("Download failed. No file created.")
            except Exception as e:
                st.error(f"Process failed: {e}")

    # --- RESULT DOWNLOADS ---
    if st.session_state.get('ready_segment'):
        d = st.session_state['ready_segment']
        st.download_button(f"💾 Save Video Segment", d['data'], d['name'], "video/mp4")

    if len(st.session_state.get('captured_images', [])) > 0:
        st.divider()
        st.success(f"🎉 **Results Ready:** {len(st.session_state['captured_images'])} Slides Captured")
        
        st.subheader("📄 Download PDF")
        pdf_path = create_pdf(st.session_state['captured_images'])
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f.read(), "slides.pdf", "application/pdf")
