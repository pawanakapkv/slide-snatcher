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
# Removed PIL/Image imports as PDF generation is no longer needed

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Slide Snatcher", layout="wide")
st.title("📸 YouTube Slide Snatcher (Download & Scan Mode)")
st.markdown("Step 1: Download video segment to server. Step 2: Auto-scan for slides.")

# Check for FFmpeg (Modified: We will try to proceed without it)
if not shutil.which('ffmpeg'):
    st.info("ℹ️ FFmpeg not detected. Using **Video Only** mode. This works fine for downloading raw video segments.")

# --- SESSION STATE INITIALIZATION ---
if 'video_info' not in st.session_state:
    st.session_state['video_info'] = None
if 'url_input' not in st.session_state:
    st.session_state['url_input'] = ""
if 'captured_images' not in st.session_state:
    st.session_state['captured_images'] = []

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
        st.warning("⚠️ No 'cookies' found in secrets!")
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
    ydl_opts = {'quiet': True, 'no_warnings': True, 'logger': logger, 'nocheckcertificate': True}
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
    st.subheader("2. Select Quality (Video Only)")
    formats = info.get('formats', [])
    unique_heights = set()
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('height'): 
            unique_heights.add(f['height'])
    sorted_heights = sorted(unique_heights, reverse=True)
    
    quality_options = {}
    for h in sorted_heights: 
        # MODIFIED: Video Only to avoid FFmpeg dependency for merging
        quality_options[f"{h}p"] = f"bestvideo[height<={h}]"
    quality_options["Best Available"] = "bestvideo"
    
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
        
        # --- DOWNLOAD RANGES CALLBACK ---
        def download_range_func(info_dict, ydl):
            return [{'start_time': start_val, 'end_time': end_val}]

        # Temporary Directory for Download & Scan
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'proxy': proxy_url,
                'cookiefile': cookies_path,
                'quiet': True,
                'no_warnings': True,
                # Add download ranges to download only the specific segment
                'download_ranges': download_range_func,
                # Removed force_keyframes_at_cuts since we are avoiding ffmpeg dependencies
            }

            try:
                # 1. DOWNLOAD
                with st.spinner("Downloading video segment to server (Video Only)..."):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                
                # Check file
                files = os.listdir(tmp_dir)
                if files:
                    file_name = files[0]
                    file_path = os.path.join(tmp_dir, file_name)
                    
                    # Read the video file bytes for the download button later
                    with open(file_path, "rb") as f:
                        video_bytes = f.read()

                    # 2. SCANNING LOGIC (Using local file)
                    status_text.info(f"📂 Scanning local file: {file_name}")
                    
                    cap = cv2.VideoCapture(file_path)
                    if not cap.isOpened():
                        st.error("Error opening downloaded video file.")
                    else:
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        if fps <= 0: fps = 30
                        
                        last_frame_data = None
                        
                        # Since we downloaded ONLY the segment, the file starts at 0:00
                        # which corresponds to 'start_val' in the original video.
                        current_frame_pos = 0 
                        
                        # We scan the entire downloaded clip
                        total_frames_in_file = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        end_frame_pos = total_frames_in_file
                        
                        # Set initial position (start of the file)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        
                        # Image processing vars
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
                                # Correct timestamp: File Time + Original Start Time
                                current_file_time = current_frame_pos / fps
                                actual_video_time = current_file_time + start_val
                                time_str = fmt_time(actual_video_time)
                                
                                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                # Show the detected slide on screen
                                st.image(img_rgb, caption=f"Found at {time_str}", channels="RGB")
                                
                                # Update position
                                last_frame_data = gray
                                current_frame_pos += jump_large 
                            else:
                                current_frame_pos += jump_small
                        
                        cap.release()
                        progress_bar.empty()
                        status_text.success(f"✅ Scanning Complete!")
                        
                        # 3. DOWNLOAD BUTTON (Instead of PDF)
                        st.divider()
                        st.subheader("⬇️ Download Segment")
                        st.download_button(
                            label=f"Download Video Clip ({file_name})",
                            data=video_bytes,
                            file_name=file_name,
                            mime="application/octet-stream"
                        )

                else:
                    st.error("Download finished but file not found on server.")
            except Exception as e:
                st.error(f"Process failed: {e}")
