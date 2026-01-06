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
st.title("📥 YouTube Downloader (Server Base)")
st.markdown("Step 1: Download video to server using Proxy & Cookies.")

# Check for FFmpeg (Minimal check as requested)
if not shutil.which('ffmpeg'):
    st.warning("⚠️ FFmpeg is not installed. Merging video+audio might fail.")

# --- SESSION STATE INITIALIZATION ---
if 'video_info' not in st.session_state:
    st.session_state['video_info'] = None
if 'url_input' not in st.session_state:
    st.session_state['url_input'] = ""

# --------------------------------------------------------------------------
# PROXY & AUTHENTICATION SETUP (FROM SECRETS)
# --------------------------------------------------------------------------
# Retrieve proxy from Streamlit secrets
proxy_url = None
if "proxy_url" in st.secrets:
    proxy_url = st.secrets["proxy_url"]
else:
    st.warning("⚠️ No 'proxy_url' found in secrets! Downloads might fail due to IP blocking.")

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

# 2. SIDEBAR SETTINGS (KEPT AS REQUESTED)
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
    def __init__(self):
        self.logs = []
    def debug(self, msg): 
        if "debug" in msg.lower(): return
        self.logs.append(f"[DEBUG] {msg}")
    def info(self, msg): 
        self.logs.append(f"[INFO] {msg}")
    def warning(self, msg): 
        self.logs.append(f"[WARN] {msg}")
    def error(self, msg): 
        self.logs.append(f"[ERROR] {msg}")

# --- HELPER: GET METADATA ---
def get_video_info(youtube_url, cookies_file=None, proxy=None):
    logger = MyLogger()
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'logger': logger, 
        'nocheckcertificate': True,
    }
    if cookies_file: ydl_opts['cookiefile'] = cookies_file
    if proxy: ydl_opts['proxy'] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(youtube_url, download=False), None
    except Exception as e:
        return None, f"{str(e)}\n\nLogs:\n" + "\n".join(logger.logs)

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
    st.subheader("2. Select Quality to Download")
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
    quality_options["Audio Only (MP3)"] = "audio_only"

    selected_q_label = st.selectbox("Choose quality:", list(quality_options.keys()))
    
    if st.button("Download to Server ⬇️", type="primary"):
        # Progress hooks
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

        # Setup Options
        format_str = quality_options[selected_q_label]
        postprocessors = []
        if "Audio Only" in selected_q_label:
            format_str = 'bestaudio/best'
            postprocessors = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]

        # Temporary Directory for Download
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'postprocessors': postprocessors,
                'proxy': proxy_url,
                'cookiefile': cookies_path,
                'quiet': True,
                'no_warnings': True,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # Check file
                files = os.listdir(tmp_dir)
                if files:
                    file_name = files[0]
                    file_path = os.path.join(tmp_dir, file_name)
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                    
                    st.success(f"✅ Downloaded '{file_name}' to server!")
                    st.download_button(
                        label="💾 Save to Local Device",
                        data=file_data,
                        file_name=file_name,
                        mime="application/octet-stream"
                    )
                else:
                    st.error("Download finished but file not found.")
            except Exception as e:
                st.error(f"Download failed: {e}")
