import streamlit as st
import os
import sys
import shutil
import tempfile
from datetime import datetime

# Try to import yt_dlp
try:
    import yt_dlp
except ImportError:
    st.error("Error: `yt_dlp` is not installed.")
    st.code("pip install yt-dlp", language="bash")
    st.stop()

# Page configuration
st.set_page_config(page_title="YouTube Downloader", page_icon="📺")

st.title("📺 YouTube Video Downloader")

# Check for FFmpeg
if not shutil.which('ffmpeg'):
    st.warning("⚠️ FFmpeg is not installed or not found in system PATH.")
    st.info("Without FFmpeg, downloads may be limited to 720p, and Audio conversion to MP3 will not work.")

# --------------------------------------------------------------------------
# PROXY & AUTHENTICATION SETUP (FROM SECRETS)
# --------------------------------------------------------------------------
# Retrieve proxy from Streamlit secrets
proxy_url = None
if "proxy_url" in st.secrets:
    proxy_url = st.secrets["proxy_url"]
else:
    st.warning("⚠️ No 'proxy_url' found in secrets! Downloads will likely fail in production.")

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
        # yt-dlp needs a file path, it cannot take a raw string
        fp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
        fp.write(cookies_content)
        fp.close()
        return fp.name
    except Exception as e:
        st.error(f"Error setting up cookies: {e}")
        return None

# Get the path to the auto-generated cookies file
cookie_path = setup_cookies_file()

# --------------------------------------------------------------------------
# APP LOGIC
# --------------------------------------------------------------------------

st.markdown("Enter a YouTube URL below to download video or audio.")

# Initialize session state to store video info between re-runs
if 'video_info' not in st.session_state:
    st.session_state.video_info = None
if 'current_url' not in st.session_state:
    st.session_state.current_url = ""

# Input URL
url = st.text_input("Enter Video URL:", placeholder="https://www.youtube.com/watch?v=...")

# Reset info if URL changes
if url != st.session_state.current_url:
    st.session_state.video_info = None
    st.session_state.current_url = url

# Fetch Info Button
if st.button("Fetch Info"):
    if not url:
        st.warning("Please enter a valid URL.")
    else:
        with st.spinner("Fetching video information..."):
            try:
                # Basic options for fetching metadata
                ydl_opts_info = {
                    'quiet': True, 
                    'no_warnings': True,
                    # Apply Proxy if available
                    'proxy': proxy_url,
                    # Apply Cookies automatically
                    'cookiefile': cookie_path,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info = ydl.extract_info(url, download=False)
                    st.session_state.video_info = info
            except Exception as e:
                st.error(f"Error fetching info: {e}")

# Display Info and Download Options if info is available
if st.session_state.video_info:
    info = st.session_state.video_info
    
    st.divider()
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.image(info.get('thumbnail'), use_container_width=True)
    
    with col2:
        st.subheader(info.get('title', 'Unknown Title'))
        st.text(f"Channel: {info.get('uploader', 'Unknown')}")
        st.text(f"Duration: {info.get('duration_string', 'Unknown')}")
    
    st.divider()
    
    # Quality Selection
    st.subheader("Download Settings")
    
    # Dynamic Quality Options based on available formats
    formats = info.get('formats', [])
    unique_heights = set()
    for f in formats:
        # Filter for video streams with valid height
        if f.get('vcodec') != 'none' and f.get('height'):
            unique_heights.add(f['height'])
    
    sorted_heights = sorted(unique_heights, reverse=True)
    
    quality_options = {
        "Best Available (Video + Audio)": "bestvideo+bestaudio/best"
    }
    
    for h in sorted_heights:
        quality_options[f"{h}p"] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
        
    quality_options["Audio Only (MP3)"] = "audio_only"
    
    selected_label = st.selectbox("Select Quality", list(quality_options.keys()))
    
    # --- CHANGED: Removed manual folder input. Use Temp Dir + Download Button instead ---
    if st.button("Start Processing & Download", type="primary"):
        # Progress Bar and Status placeholders
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    p = d.get('_percent_str', '0%').replace('%', '')
                    if p and p != 'N/A':
                        progress = float(p) / 100
                        progress_bar.progress(min(progress, 1.0))
                    
                    status_msg = f"Downloading: {d.get('_percent_str')} "
                    if d.get('_eta_str'):
                        status_msg += f"- ETA: {d.get('_eta_str')}"
                    status_text.text(status_msg)
                except Exception:
                    pass
            elif d['status'] == 'finished':
                progress_bar.progress(1.0)
                status_text.text("Download complete. Preparing file for you...")

        # Prepare Options
        format_str = quality_options[selected_label]
        postprocessors = []
        
        if "Audio Only" in selected_label:
            format_str = 'bestaudio/best'
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        # Use a Temporary Directory to store the file on the server
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'postprocessors': postprocessors,
                'proxy': proxy_url, 
                'cookiefile': cookie_path,
            }
            
            # Start Download
            download_success = False
            try:
                if proxy_url:
                    st.info(f"Connecting via Proxy...")
                
                with st.spinner("Downloading video to server..."):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                download_success = True
            except Exception as e:
                st.error(f"❌ Download failed: {e}")

            # If successful, find the file and offer it to the user
            if download_success:
                try:
                    # Find the downloaded file in the temp dir
                    files = os.listdir(tmp_dir)
                    if files:
                        file_name = files[0]
                        file_path = os.path.join(tmp_dir, file_name)
                        
                        # Read file into memory
                        with open(file_path, "rb") as f:
                            file_data = f.read()
                        
                        st.success("✅ Ready! Click the button below to save to your device.")
                        st.download_button(
                            label=f"⬇️ Save '{file_name}' to Downloads",
                            data=file_data,
                            file_name=file_name,
                            mime="application/octet-stream"
                        )
                    else:
                        st.error("Download finished, but file not found on server.")
                except Exception as e:
                    st.error(f"Error preparing download: {e}")
