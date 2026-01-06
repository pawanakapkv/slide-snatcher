import streamlit as st
import streamlit.components.v1 as components
import cv2
import yt_dlp
import numpy as np
import os
import tempfile
import sys
import shutil
from PIL import Image

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Slide Snatcher", layout="wide")
st.title("📸 YouTube Slide Snatcher (Low RAM Mode)")
st.markdown("Paste a lecture link, **Select Quality**, set the **Time Range**, and I will scan for slides **without downloading** the whole file.")

# Check for FFmpeg (Minimal check as requested)
if not shutil.which('ffmpeg'):
    st.warning("⚠️ FFmpeg is not installed. Video stream processing might fail.")

# --- SESSION STATE INITIALIZATION ---
if 'captured_images' not in st.session_state:
    st.session_state['captured_images'] = [] # Stores compressed JPG buffers
if 'video_info' not in st.session_state:
    st.session_state['video_info'] = None
if 'url_input' not in st.session_state:
    st.session_state['url_input'] = ""

# --- ADSTERRA CONFIGURATION ---
ADSTERRA_DIRECT_LINK = "https://www.google.com" # REPLACE THIS

# --------------------------------------------------------------------------
# PROXY & AUTHENTICATION SETUP (FROM SECRETS)
# --------------------------------------------------------------------------
# Retrieve proxy from Streamlit secrets
proxy_url = None
if "proxy_url" in st.secrets:
    proxy_url = st.secrets["proxy_url"]
else:
    st.warning("⚠️ No 'proxy_url' found in secrets! Scanning might fail due to IP blocking.")

# Setup Cookies from Secrets
@st.cache_resource
def setup_cookies_file():
    """Reads cookies from st.secrets and writes them to a temp file."""
    if "cookies" not in st.secrets:
        st.warning("⚠️ No 'cookies' found in secrets! You may encounter 'Sign in' errors.")
        return None
        
    try:
        # Get cookies string from secrets
        cookies_content = st.secrets["cookies"]
        
        # Create a temp file that persists for the session
        fp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
        fp.write(cookies_content)
        fp.close()
        return fp.name
    except Exception as e:
        st.error(f"Error setting up cookies: {e}")
        return None

# Get the path to the auto-generated cookies file
cookies_path = setup_cookies_file()

# 2. SIDEBAR SETTINGS
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.subheader("🔍 Detection Settings")
    sensitivity = st.slider("Color Sensitivity", min_value=10, max_value=100, value=35, help="Higher = less sensitive to small color changes")
    strictness = st.slider("Strictness (%)", min_value=0.1, max_value=100.0, value=1.0, step=0.1, help="Percentage of screen that must change to trigger a capture")
    
    st.divider()
    st.info("💡 **Speed Tip:** 'Scan Frequency' is now dynamic!")
    min_skip = st.slider("Min Jump (Seconds)", 1, 5, 2)
    max_skip = st.slider("Max Jump (Seconds)", 5, 30, 10)

# --- CUSTOM LOGGER FOR DEBUGGING ---
class MyLogger:
    def debug(self, msg): pass
    def info(self, msg): print(f"[YTDLP-INFO] {msg}"); sys.stdout.flush()
    def warning(self, msg): print(f"[YTDLP-WARN] {msg}"); sys.stdout.flush()
    def error(self, msg): print(f"[YTDLP-ERROR] {msg}"); sys.stdout.flush()

# --- HELPER 1: GET METADATA ---
def get_video_info(youtube_url, cookies_file=None, proxy=None):
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'logger': MyLogger(), 
        'nocheckcertificate': True
    }
    if cookies_file: ydl_opts['cookiefile'] = cookies_file
    if proxy: ydl_opts['proxy'] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Return info AND None for error
            return ydl.extract_info(youtube_url, download=False), None
    except Exception as e:
        # Return None for info AND the error string
        return None, str(e)

# --- HELPER 2: GET STREAM URL (NO DOWNLOAD) ---
def get_stream_url(youtube_url, format_str, cookies_file=None, proxy=None):
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'nocheckcertificate': True, 
        'ignoreerrors': True, 
        'logger': MyLogger(), 
        'format': format_str
    }
    if cookies_file: ydl_opts['cookiefile'] = cookies_file
    if proxy: ydl_opts['proxy'] = proxy
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            
            # --- FIX: Check if info is None before accessing attributes ---
            if info is None:
                return None, None, "Failed to extract video info (None returned). This often happens due to geo-restrictions or age-gating. Check if cookies are valid."

            # Return URL, FPS, and None for error
            return info.get('url', None), info.get('fps', 30), None
    except Exception as e:
        # Return None, None, and the error string
        return None, None, str(e)

# --- HELPER 3: CREATE SLIDESHOW VIDEO ---
def create_summary_video(image_buffers):
    if not image_buffers: return None
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, "summary_slideshow.mp4")
    
    # Decode the first image to determine dimensions
    first_img = cv2.imdecode(image_buffers[0], cv2.IMREAD_COLOR)
    height, width, layers = first_img.shape
    
    # cv2.VideoWriter requires a numerical FourCC code, but opencv-python handles string passing usually.
    # We use 'mp4v' which is widely supported.
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    out = cv2.VideoWriter(output_path, fourcc, 0.5, (width, height)) 
    
    for buf in image_buffers:
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None: continue
        if img.shape[0] != height or img.shape[1] != width:
            img = cv2.resize(img, (width, height))
        out.write(img)
        
    out.release()
    return output_path

# --- HELPER 4: CREATE PDF ---
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

# --- FORMATTING HELPER ---
def fmt_time(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60); 
    if hours > 0: return f"{int(hours)}h {int(mins)}m {int(secs)}s"
    return f"{int(mins)}m {int(secs)}s"

# 4. MAIN APP INTERFACE
url = st.text_input("1. Enter YouTube URL:", value=st.session_state['url_input'], placeholder="https://www.youtube.com/watch?v=...")

if st.button("Check Video 🔎"):
    if not url:
        st.error("Please enter a URL.")
    else:
        with st.spinner("Fetching video formats..."):
            # Pass proxy and cookies here
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
        if info.get('thumbnail'): st.image(info['thumbnail'], use_container_width=True) # Fixed width error
    with col_b:
        st.subheader(info.get('title', 'Unknown'))
        duration = info.get('duration', 0)
        st.write(f"**Total Duration:** {fmt_time(duration)}")
    
    # --- QUALITY SELECTION ---
    st.write("### 2. Select Video Quality (Video Only)")
    formats = info.get('formats', [])
    unique_heights = set()
    for f in formats:
        # Relaxed filtering: Removed requirement for 'http' protocol to allow more streams
        if f.get('vcodec') != 'none' and f.get('height'): 
            unique_heights.add(f['height'])
    sorted_heights = sorted(unique_heights, reverse=True)
    
    quality_options = {}
    for h in sorted_heights: 
        # Removed [protocol^=http] to allow HLS/DASH streams which FFmpeg handles well
        quality_options[f"{h}p (Stream)"] = f"bestvideo[height={h}]"
    
    quality_options["Best Available (Stream)"] = "bestvideo"

    selected_q_label = st.selectbox("Choose quality to scan:", list(quality_options.keys()))
    selected_format_str = quality_options[selected_q_label]

    # --- TIME RANGE SELECTION ---
    st.write("### 3. Select Time Range to Scan")
    start_val, end_val = st.slider("Drag sliders to select start and end points:", min_value=0, max_value=duration, value=(0, duration), format="mm:ss")
    
    st.info(f"⏱️ Will scan **{selected_q_label}** from **{fmt_time(start_val)}** to **{fmt_time(end_val)}**")

    # --- CONTROLS ---
    col_start, col_stop = st.columns(2)
    start_btn = col_start.button("Start Live Scan 🚀", type="primary")
    stop_btn = col_stop.button("Stop & Save ⏹️")

    # LOGIC: Start Scan
    if start_btn:
        # Wrap everything in a try-except to catch generic crashes (OpenCV errors, etc)
        try:
            st.session_state['captured_images'] = []
            
            js = f"window.open('{ADSTERRA_DIRECT_LINK}', '_blank');"
            components.html(f"<script>{js}</script>", height=0, width=0)
            
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            status_text.info(f"🌐 Fetching stream URL via Proxy...")
            # Pass proxy and cookies here
            stream_url, meta_fps, stream_error = get_stream_url(url, selected_format_str, cookies_path, proxy_url)
            
            if not stream_url:
                st.error(f"❌ Could not retrieve stream URL.\n\nError details: {stream_error}")
            else:
                status_text.info(f"🎥 Connecting to stream...")
                
                # --- CRITICAL FIX: FORCE OPENCV TO USE PROXY ---
                if proxy_url:
                    os.environ['http_proxy'] = proxy_url
                    os.environ['https_proxy'] = proxy_url
                    os.environ['HTTP_PROXY'] = proxy_url
                    os.environ['HTTPS_PROXY'] = proxy_url
                
                # Explicitly use FFmpeg backend for Streamlit Cloud/Linux environments
                cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
                
                if not cap.isOpened():
                    st.error("Error connecting to video stream. OpenCV could not open the URL. Ensure FFmpeg is installed and the proxy allows video streaming.")
                else:
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    if fps <= 0 or fps > 120: fps = meta_fps if meta_fps else 30
                    
                    last_frame_data = None
                    current_frame_pos = int(start_val * fps)
                    end_frame_pos = int(end_val * fps)
                    total_scan_frames = end_frame_pos - current_frame_pos
                    
                    # Seek to start
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_pos)
                    ret, frame = cap.read()
                    
                    if not ret:
                        st.error("Stream ended unexpectedly or seek failed immediately. The video format might not be supported by OpenCV/FFmpeg.")
                    else:
                        orig_h, orig_w = frame.shape[:2]
                        process_w = 640
                        process_h = int(process_w * (orig_h / orig_w)) if orig_w > 0 else 360
                        total_pixel_count = process_w * process_h
                        motion_threshold_score = int(total_pixel_count * (strictness / 100) * 255)
                        jump_small = int(fps * min_skip)
                        jump_large = int(fps * max_skip)
                        
                        st.divider()
                        st.subheader("Results (Live Stream)")
                        
                        while current_frame_pos < end_frame_pos:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_pos)
                            ret, frame = cap.read()
                            if not ret: break 
                            
                            if total_scan_frames > 0:
                                relative_pos = current_frame_pos - int(start_val * fps)
                                progress_bar.progress(min(relative_pos / total_scan_frames, 1.0))

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
                                
                                time_str = fmt_time(current_frame_pos / fps)
                                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                st.image(img_rgb, caption=f"Slide #{len(st.session_state['captured_images'])} at {time_str}", channels="RGB")
                                current_frame_pos += jump_large 
                            else:
                                current_frame_pos += jump_small

                        cap.release()
                        progress_bar.empty()
                        status_text.success(f"✅ Scanning Complete! Found {len(st.session_state['captured_images'])} slides.")
                        
                # --- CLEANUP PROXY ENV VARS (Optional but good practice) ---
                if proxy_url:
                    os.environ.pop('http_proxy', None)
                    os.environ.pop('https_proxy', None)
                    os.environ.pop('HTTP_PROXY', None)
                    os.environ.pop('HTTPS_PROXY', None)
                    
        except Exception as e:
            st.error(f"❌ An unexpected error occurred:\n\n{e}")

    # --- RESULT DISPLAY ---
    if len(st.session_state.get('captured_images', [])) > 0:
        if stop_btn:
             st.warning("⚠️ Scanning stopped by user. Showing results captured so far...")
        
        st.divider()
        st.success(f"🎉 **Results Ready:** {len(st.session_state['captured_images'])} Slides Captured")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Download PDF")
            pdf_path = create_pdf(st.session_state['captured_images'])
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f.read(), "slides.pdf", "application/pdf")

        with col2:
            st.subheader("⏩ Download Video")
            summary_path = create_summary_video(st.session_state['captured_images'])
            if summary_path and os.path.exists(summary_path):
                with open(summary_path, "rb") as f:
                    st.download_button("Download Slideshow", f.read(), "slideshow.mp4", "video/mp4")
