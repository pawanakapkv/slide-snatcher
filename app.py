import streamlit as st
import cv2
import yt_dlp
import numpy as np
import os
import tempfile
import shutil
from PIL import Image

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Slide Snatcher", layout="wide")
st.title("📸 YouTube Slide Snatcher")
st.markdown("Step 1: Download video segment. Step 2: Auto-scan for slides.")

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

# --------------------------------------------------------------------------
# SETTINGS (SIDEBAR)
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.subheader("🔍 Detection Settings")
    sensitivity = st.slider("Color Sensitivity", min_value=10, max_value=100, value=35, help="Higher = less sensitive to small color changes")
    strictness = st.slider("Strictness (%)", min_value=0.1, max_value=100.0, value=1.0, step=0.1, help="Percentage of screen that must change to trigger capture")
    
    st.divider()
    st.subheader("⏩ Speed")
    min_skip = st.slider("Min Jump (Seconds)", 1, 5, 2)
    max_skip = st.slider("Max Jump (Seconds)", 5, 30, 10)

# --------------------------------------------------------------------------
# PROXY & AUTH LOGIC
# --------------------------------------------------------------------------
proxy_url = st.secrets.get("proxy_url", None)

def get_cookies_path(text_input, uploaded_file):
    """
    Returns path to a temp cookie file. 
    Priority: 1. Paste Text, 2. Uploaded File, 3. st.secrets, 4. None
    """
    try:
        content = None
        
        # PRIORITY 1: Pasted Text
        if text_input and len(text_input.strip()) > 0:
            content = text_input
            
        # PRIORITY 2: Manual Upload
        elif uploaded_file is not None:
            content = uploaded_file.getvalue().decode("utf-8")

        # PRIORITY 3: Secrets
        elif "cookies" in st.secrets:
            content = st.secrets["cookies"]

        # Write to temp file if we found content
        if content:
            fp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
            fp.write(content)
            fp.close()
            return fp.name
            
    except Exception as e:
        st.error(f"Error processing cookies: {e}")
        return None
    
    return None

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
    # Robust options for fetching metadata
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

# --- COOKIE SECTION (Moved to Main Area) ---
with st.expander("🍪 Authentication (Fix 'Sign in' errors)", expanded=False):
    st.info("If you see a 'Sign in to confirm you're not a bot' error, paste your cookies below.")
    col1, col2 = st.columns(2)
    with col1:
        cookie_text_input = st.text_area("Paste Cookies Text (Netscape Format)", height=150, help="Paste the content of your cookies.txt here.")
    with col2:
        uploaded_cookies = st.file_uploader("Or Upload cookies.txt", type=["txt"])

# Resolve cookies path immediately
cookies_path = get_cookies_path(cookie_text_input, uploaded_cookies)

if st.button("Fetch Info 🔎"):
    if not url:
        st.error("Please enter a URL.")
    else:
        with st.spinner("Fetching video info..."):
            info, error_msg = get_video_info(url, cookies_file=cookies_path, proxy=proxy_url)
            if info:
                st.session_state['video_info'] = info
                st.session_state['url_input'] = url 
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
    start_val, end_val = st.slider("Drag sliders to select scan range:", min_value=0, max_value=duration, value=(0, duration), format="mm:ss")
    st.info(f"⏱️ Will download and scan only from **{fmt_time(start_val)}** to **{fmt_time(end_val)}**")
    
    if st.button("Download & Scan 🚀", type="primary"):
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

        # Setup Options
        format_str = quality_options[selected_q_label]
        
        def download_range_func(info_dict, ydl):
            return [{'start_time': start_val, 'end_time': end_val}]

        # Temporary Directory for Download & Scan
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'proxy': proxy_url,
                'cookiefile': cookies_path, # Uses uploaded file or secret
                'quiet': True,
                'no_warnings': True,
                'download_ranges': download_range_func,
                'force_keyframes_at_cuts': True,
                # FIXED: Options to avoid blocking
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }

            try:
                # 1. DOWNLOAD
                with st.spinner("Downloading video segment to server..."):
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                    except Exception as e:
                        # FALLBACK: If cookies failed, try without them
                        if "cookie" in str(e).lower() or "Sign in" in str(e):
                            st.warning("⚠️ Cookie auth failed. Retrying without cookies...")
                            if 'cookiefile' in ydl_opts: del ydl_opts['cookiefile']
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([url])
                        else:
                            raise e
                
                # Check file
                files = os.listdir(tmp_dir)
                if files:
                    file_name = files[0]
                    file_path = os.path.join(tmp_dir, file_name)
                    
                    # 2. SCANNING LOGIC (Using local file)
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
                                
                                # Correct timestamp: File Time + Original Start Time
                                current_file_time = current_frame_pos / fps
                                actual_video_time = current_file_time + start_val
                                time_str = fmt_time(actual_video_time)
                                
                                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                st.image(img_rgb, caption=f"Slide #{len(st.session_state['captured_images'])} at {time_str}", channels="RGB")
                                current_frame_pos += jump_large 
                            else:
                                current_frame_pos += jump_small
                        
                        cap.release()
                        progress_bar.empty()
                        status_text.success(f"✅ Scanning Complete! Found {len(st.session_state['captured_images'])} slides.")
                else:
                    st.error("Download finished but file not found on server.")
            except Exception as e:
                st.error(f"Process failed: {e}")

    # --- RESULT DOWNLOADS ---
    if len(st.session_state.get('captured_images', [])) > 0:
        st.divider()
        st.success(f"🎉 **Results Ready:** {len(st.session_state['captured_images'])} Slides Captured")
        
        st.subheader("📄 Download PDF")
        pdf_path = create_pdf(st.session_state['captured_images'])
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f.read(), "slides.pdf", "application/pdf")
