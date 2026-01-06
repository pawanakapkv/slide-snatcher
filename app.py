import streamlit as st
import cv2
import yt_dlp
import numpy as np
import os
import tempfile
import shutil
from math import ceil
from PIL import Image

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Slide Snatcher", layout="wide", page_icon="📸")
st.title("📸 YouTube Slide Snatcher (Refined)")
st.markdown("Step 1: Fetch Video. Step 2: Select **Segments** or **Chapters**. Step 3: Download & Scan.")

# Check for FFmpeg (Crucial for merging video+audio, though we mostly need video here)
if not shutil.which('ffmpeg'):
    st.warning("⚠️ FFmpeg not detected. Downloads will fallback to the best single file available (usually 720p or 360p) and frame accuracy might be lower.")

# --- SESSION STATE INITIALIZATION ---
if 'video_info' not in st.session_state:
    st.session_state['video_info'] = None
if 'url_input' not in st.session_state:
    st.session_state['url_input'] = ""
if 'captured_images' not in st.session_state:
    st.session_state['captured_images'] = []
if 'ready_segment' not in st.session_state:
    st.session_state['ready_segment'] = None 

# --- LOGGER CLASS ---
class MyLogger:
    def __init__(self): self.logs = []
    def debug(self, msg): pass
    def info(self, msg): self.logs.append(f"[INFO] {msg}")
    def warning(self, msg): self.logs.append(f"[WARN] {msg}")
    def error(self, msg): self.logs.append(f"[ERROR] {msg}")

# --- HELPERS ---
def fmt_time(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0: return f"{int(hours)}h {int(mins)}m {int(secs)}s"
    return f"{int(mins)}m {int(secs)}s"

def get_video_info(youtube_url, cookies_file=None, proxy_url=None):
    logger = MyLogger()
    # Basic options to just fetch metadata
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'logger': logger, 
        'nocheckcertificate': True,
        # 'web' is usually the safest client for metadata. 
        # heavily forcing android/ios without cookies often triggers bot detection.
        'extractor_args': {'youtube': {'player_client': ['web']}},
    }
    
    if cookies_file: 
        ydl_opts['cookiefile'] = cookies_file
        # If we have cookies, we can try more robust clients
        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'web']}}
    
    if proxy_url and proxy_url.strip():
        ydl_opts['proxy'] = proxy_url.strip()

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
        # Decode numpy array to image
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None: continue
        # Convert BGR (OpenCV) to RGB (PIL)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_images.append(Image.fromarray(img_rgb))
    
    if pil_images:
        pil_images[0].save(output_path, "PDF", resolution=100.0, save_all=True, append_images=pil_images[1:])
        return output_path
    return None

# 2. SIDEBAR SETTINGS
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.subheader("🌐 Network")
    
    # Try to load proxy from secrets
    default_proxy = ""
    try:
        if "PROXY_URL" in st.secrets:
            default_proxy = st.secrets["PROXY_URL"]
    except:
        pass # Ignore if secrets file is missing or key error

    proxy_input = st.text_input("Proxy URL (Optional)", value=default_proxy, placeholder="http://user:pass@host:port", help="Leave empty to use your local IP. Loaded from secrets if available.")

    st.subheader("🍪 Authentication")
    st.markdown("Upload `cookies.txt` (Netscape format) if the video is age-gated.")
    uploaded_cookies = st.file_uploader("Upload cookies.txt", type=['txt'])
    
    cookies_path = None
    if uploaded_cookies:
        try:
            # Create a temp file that persists just for this run
            # We use delete=False and manage cleanup implicitly by OS temp clearing or rewrite
            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='wb') as fp:
                fp.write(uploaded_cookies.getvalue())
                cookies_path = fp.name
            st.success("✅ Cookies loaded")
        except Exception as e:
            st.error(f"Error loading cookies: {e}")

    st.divider()
    
    st.subheader("🔍 Slide Detection")
    sensitivity = st.slider("Color Sensitivity", 10, 100, 35, help="Higher = less sensitive to small lighting changes")
    strictness = st.slider("Screen Change %", 0.1, 50.0, 1.0, 0.1, help="How much of the screen must change to capture a new slide?")
    
    st.divider()
    st.markdown("**Scanning Speed**")
    min_skip = st.slider("Min Jump (Sec)", 1, 5, 2)
    max_skip = st.slider("Max Jump (Sec)", 5, 60, 10)

# 3. MAIN INTERFACE
url = st.text_input("1. YouTube URL:", value=st.session_state['url_input'], placeholder="https://www.youtube.com/watch?v=...")

if st.button("Fetch Info 🔎", type="primary"):
    if not url:
        st.error("Please enter a URL.")
    else:
        with st.spinner("Fetching metadata..."):
            # Reset state on new fetch
            st.session_state['ready_segment'] = None
            st.session_state['captured_images'] = []
            
            info, error_msg = get_video_info(url, cookies_file=cookies_path, proxy_url=proxy_input)
            
            if info:
                st.session_state['video_info'] = info
                st.session_state['url_input'] = url 
                st.rerun() 
            else:
                st.error(f"❌ Error fetching video:\n{error_msg}")

# 4. VIDEO PROCESSING UI
if st.session_state['video_info'] and url == st.session_state['url_input']:
    info = st.session_state['video_info']
    
    st.divider()
    c1, c2 = st.columns([1, 3])
    with c1:
        if info.get('thumbnail'): st.image(info['thumbnail'], use_container_width=True)
    with c2:
        st.subheader(info.get('title', 'Unknown Title'))
        st.caption(f"Channel: {info.get('uploader', 'Unknown')} | Duration: {fmt_time(info.get('duration', 0))}")

    # --- QUALITY SELECTOR ---
    st.subheader("2. Select Quality")
    # Simplify quality selection to prevent "Format not available" errors
    # We offer "Best" and strict height limits
    quality_map = {
        "Best Available": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    }
    selected_quality = st.selectbox("Max Resolution:", list(quality_map.keys()), index=1)
    selected_format_str = quality_map[selected_quality]

    # --- SEGMENT SELECTOR ---
    st.subheader("3. Select Range")
    chapters = info.get('chapters')
    start_time, end_time = 0, info.get('duration', 0)
    
    use_chapters = False
    if chapters:
        use_chapters = st.checkbox(f"Use Chapters ({len(chapters)} found)", value=True)
        if use_chapters:
            chap_opts = [f"{i+1}. {c['title']} ({fmt_time(c['start_time'])})" for i, c in enumerate(chapters)]
            s_idx, e_idx = st.select_slider("Select Chapter Range", options=range(len(chapters)), value=(0, len(chapters)-1), format_func=lambda i: chap_opts[i])
            start_time = chapters[s_idx]['start_time']
            end_time = chapters[e_idx]['end_time']
            st.info(f"📍 Downloading from **{chapters[s_idx]['title']}** to **{chapters[e_idx]['title']}**")
    
    if not use_chapters:
        # Simple slider for custom range
        col_s1, col_s2 = st.columns(2)
        start_time = col_s1.number_input("Start Time (sec)", 0, int(info.get('duration', 0)), 0)
        end_time = col_s2.number_input("End Time (sec)", 0, int(info.get('duration', 0)), int(info.get('duration', 0)))
        if start_time >= end_time:
            st.error("Start time must be less than end time.")

    # --- DOWNLOAD LOGIC ---
    def run_download_and_scan(mode="scan"):
        st.session_state['captured_images'] = []
        progress_bar = st.progress(0)
        status_box = st.empty()
        
        # Hook for yt-dlp progress
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    p = d.get('_percent_str', '0%').replace('%', '')
                    status_box.text(f"Downloading: {d.get('_percent_str')} | ETA: {d.get('_eta_str')}")
                    if p != 'N/A': progress_bar.progress(min(float(p)/100, 1.0))
                except: pass
            elif d['status'] == 'finished':
                progress_bar.progress(1.0)
                status_box.success("Download Complete. Processing...")

        # Temp directory for download
        with tempfile.TemporaryDirectory() as tmp_dir:
            # yt-dlp download options
            dl_opts = {
                'format': selected_format_str,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
                # Safe client args
                'extractor_args': {'youtube': {'player_client': ['web', 'android']}} if cookies_path else {'youtube': {'player_client': ['web']}},
                # Range download
                'download_ranges': lambda _, __: [{'start_time': start_time, 'end_time': end_time}],
                # Fallback to just 'best' if the complex format string fails
                'ignoreerrors': True 
            }
            
            if cookies_path: dl_opts['cookiefile'] = cookies_path
            if proxy_input: dl_opts['proxy'] = proxy_input

            try:
                with st.spinner("Starting Download..."):
                    with yt_dlp.YoutubeDL(dl_opts) as ydl:
                        error_code = ydl.download([url])
                        
                # Check for files
                files = [f for f in os.listdir(tmp_dir) if os.path.isfile(os.path.join(tmp_dir, f))]
                if not files:
                    # Retry with simpler format if failed
                    status_box.warning("High quality download failed. Retrying with basic format...")
                    dl_opts['format'] = 'best'
                    with yt_dlp.YoutubeDL(dl_opts) as ydl:
                        ydl.download([url])
                    files = [f for f in os.listdir(tmp_dir) if os.path.isfile(os.path.join(tmp_dir, f))]

                if not files:
                    st.error("Download failed completely. Check cookies or proxy.")
                    return

                target_file = os.path.join(tmp_dir, files[0])
                
                # If just downloading video
                if mode == "video_only":
                    with open(target_file, "rb") as f:
                        st.session_state['ready_segment'] = {
                            'name': files[0],
                            'data': f.read()
                        }
                    status_box.success("Video ready for download below!")
                    return

                # If scanning
                status_box.info("Scanning video for slides...")
                scan_video(target_file, progress_bar)
                status_box.success("Scan Complete!")

            except Exception as e:
                st.error(f"An error occurred: {e}")

    def scan_video(filepath, progress_bar):
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened(): return
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        
        # Logic setup
        last_frame_data = None
        curr_frame = 0
        
        # Processing resolution (smaller = faster)
        proc_w, proc_h = 640, 360 
        
        threshold_px = int((proc_w * proc_h) * (strictness / 100))
        
        jump_large = int(fps * max_skip)
        jump_small = int(fps * min_skip)

        st.subheader("Results")
        res_cols = st.columns(3) # Grid for results
        col_idx = 0

        while curr_frame < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, curr_frame)
            ret, frame = cap.read()
            if not ret: break
            
            # Progress update
            if total_frames > 0:
                progress_bar.progress(min(curr_frame / total_frames, 1.0))
            
            # 1. Resize & Blur for comparison
            small = cv2.resize(frame, (proc_w, proc_h))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            is_new = False
            
            if last_frame_data is None:
                is_new = True
                last_frame_data = gray
            else:
                # 2. Compare with previous captured slide
                diff = cv2.absdiff(last_frame_data, gray)
                _, thresh = cv2.threshold(diff, sensitivity, 255, cv2.THRESH_BINARY)
                change_score = np.count_nonzero(thresh)
                
                if change_score > threshold_px:
                    is_new = True
                    last_frame_data = gray
            
            if is_new:
                # Save full res frame to memory
                ret, buf = cv2.imencode('.jpg', frame)
                if ret:
                    st.session_state['captured_images'].append(buf)
                    
                    # Show in UI
                    timestamp = fmt_time((curr_frame/fps) + start_time)
                    with res_cols[col_idx % 3]:
                        st.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), caption=f"Slide @ {timestamp}", use_container_width=True)
                    col_idx += 1
                
                # If we found a slide, jump forward a larger amount to skip animations/transitions
                curr_frame += jump_large
            else:
                # If no change, inch forward to find the change
                curr_frame += jump_small
        
        cap.release()

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("🚀 Download & Scan Slides"):
        run_download_and_scan(mode="scan")
    
    if col_btn2.button("📥 Download Clip Only"):
        run_download_and_scan(mode="video_only")

# 5. EXPORT SECTION
if st.session_state.get('captured_images'):
    st.divider()
    st.subheader("Export")
    
    pdf_path = create_pdf(st.session_state['captured_images'])
    if pdf_path:
        with open(pdf_path, "rb") as f:
            st.download_button(
                label="📄 Download All Slides (PDF)",
                data=f.read(),
                file_name="lecture_slides.pdf",
                mime="application/pdf",
                type="primary"
            )

if st.session_state.get('ready_segment'):
    st.divider()
    d = st.session_state['ready_segment']
    st.download_button(
        label=f"🎬 Download Video Clip ({d['name']})",
        data=d['data'],
        file_name=d['name'],
        mime="video/mp4"
    )
