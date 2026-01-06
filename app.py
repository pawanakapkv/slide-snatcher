import streamlit as st
import os
import sys
import shutil

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
                ydl_opts = {'quiet': True, 'no_warnings': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
    
    # Download Path (Local System)
    # Note: Since this is a local tool running via Streamlit, we can write to local disk.
    default_path = os.getcwd()
    download_path = st.text_input("Save to folder:", value=default_path)
    
    if st.button("Download Now", type="primary"):
        if not os.path.isdir(download_path):
            st.error("Invalid download path. Please check the folder location.")
        else:
            # Progress Bar and Status placeholders
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        p = d.get('_percent_str', '0%').replace('%', '')
                        # Handle cases where percentage might be 'N/A'
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
                    status_text.text("Download complete. Processing/Converting...")

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
            
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'postprocessors': postprocessors,
            }
            
            # Start Download
            try:
                with st.spinner("Starting download..."):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                st.success(f"✅ Download complete! Saved to: {download_path}")
                st.balloons()
            except Exception as e:
                st.error(f"❌ Download failed: {e}")
