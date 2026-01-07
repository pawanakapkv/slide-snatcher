import streamlit as st
import cv2
import yt_dlp
import numpy as np
import os
import tempfile
import shutil
import time
from PIL import Image

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="LectureNotes Pro", page_icon="⚡", layout="wide")

# --- SESSION STATE INITIALIZATION (CRITICAL: MUST BE AT TOP) ---
if 'setup_active' not in st.session_state:
    st.session_state['setup_active'] = False
if 'setup_step' not in st.session_state:
    st.session_state['setup_step'] = 1
if 'video_info' not in st.session_state:
    st.session_state['video_info'] = None
if 'url_input' not in st.session_state:
    st.session_state['url_input'] = ""
if 'captured_images' not in st.session_state:
    st.session_state['captured_images'] = []
if 'cookies_path' not in st.session_state:
    st.session_state['cookies_path'] = None
if 'scan_complete' not in st.session_state:
    st.session_state['scan_complete'] = False

# Config State Initialization (For persistence across wizard/workspace)
if 'sensitivity' not in st.session_state: st.session_state['sensitivity'] = 35
if 'strictness' not in st.session_state: st.session_state['strictness'] = 1.0
if 'min_skip' not in st.session_state: st.session_state['min_skip'] = 2
if 'max_skip' not in st.session_state: st.session_state['max_skip'] = 10

# Ensure step is within valid range if phase count changes
if st.session_state['setup_step'] > 6:
    st.session_state['setup_step'] = 6

# --- QUERY PARAM HANDLING (For HTML Button) ---
# Check if the HTML button was clicked via URL param
if "setup" in st.query_params:
    st.session_state['setup_active'] = True
    st.query_params.clear()

# --- ULTRA MODERN DARK THEME CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=JetBrains+Mono:wght@400;500;800&family=Oswald:wght@500;700&display=swap');

    :root {
        --bg-depth: #0f1117;
        --bg-surface: #1e293b;
        --bg-card: #161b22;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --accent-primary: #6366f1; /* Indigo */
        --accent-glow: rgba(99, 102, 241, 0.5);
        --border: #334155;
        --success: #10b981;
        --yt-red: #FF0000;
        --radius-sm: 0.375rem; /* 6px */
        --radius-md: 0.75rem;  /* 12px */
    }

    /* GLOBAL RESET */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
        color: var(--text-primary);
        background-color: var(--bg-depth);
        font-size: 1rem; /* Base relative size */
        -webkit-font-smoothing: antialiased;
    }
    
    /* Force Dark Background on Main Container with Grid */
    .stApp {
        background-color: #0b0d11;
        background-image: 
            linear-gradient(rgba(99, 102, 241, 0.05) 0.0625rem, transparent 0.0625rem),
            linear-gradient(90deg, rgba(99, 102, 241, 0.05) 0.0625rem, transparent 0.0625rem);
        background-size: 2.5rem 2.5rem; /* 40px */
        background-attachment: fixed;
    }

    /* HIDE STREAMLIT CHROME */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {
        padding-top: 1rem;
        max-width: 95rem; /* Increased width for wider layout */
    }

    /* --- TECHY HERO SECTION (ANIMATED) --- */
    .hero-container {
        position: relative;
        text-align: center;
        margin-bottom: 2rem; 
        padding: 8rem 3rem 6rem 3rem; /* Increased Size Proportionally */
        background-color: transparent; /* Transparent Background */
        background-image: none;
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        box-shadow: none;
        overflow: hidden;
        transition: all 0.3s ease;
    }

    /* Scanning Line Animation */
    .scan-line {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 0.125rem; /* 2px */
        background: linear-gradient(90deg, transparent, #6366f1, transparent);
        opacity: 0.5;
        animation: scan 3s ease-in-out infinite;
        box-shadow: 0 0 0.9375rem rgba(99, 102, 241, 0.8);
        pointer-events: none;
    }

    @keyframes scan {
        0% { top: -10%; }
        100% { top: 110%; }
    }

    /* Glitch Title Effect */
    .hero-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 4rem;
        font-weight: 800;
        color: #fff;
        text-transform: uppercase;
        letter-spacing: -0.05em;
        position: relative;
        display: inline-block;
        margin-bottom: 1rem;
        text-shadow: 0.1875rem 0.1875rem 0rem rgba(99, 102, 241, 0.8), -0.125rem -0.125rem 0rem rgba(6, 182, 212, 0.8);
    }
    
    .hero-title::before {
        content: attr(data-text);
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #0b0d11;
        opacity: 0.8;
        clip-path: polygon(0 0, 100% 0, 100% 45%, 0 45%);
        transform: translate(-0.1875rem, 0);
        animation: glitch-anim-1 2.5s infinite linear alternate-reverse;
    }
    
    .hero-title::after {
        content: attr(data-text);
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #0b0d11;
        opacity: 0.8;
        clip-path: polygon(0 55%, 100% 55%, 100% 100%, 0 100%);
        transform: translate(0.1875rem, 0);
        animation: glitch-anim-2 3s infinite linear alternate-reverse;
    }

    @keyframes glitch-anim-1 {
        0% { clip-path: inset(20% 0 80% 0); transform: translate(-0.125rem, 0.0625rem); }
        20% { clip-path: inset(60% 0 10% 0); transform: translate(0.125rem, -0.0625rem); }
        40% { clip-path: inset(40% 0 50% 0); transform: translate(-0.125rem, 0.125rem); }
        60% { clip-path: inset(80% 0 5% 0); transform: translate(0.0625rem, -0.125rem); }
        80% { clip-path: inset(10% 0 70% 0); transform: translate(-0.0625rem, 0.0625rem); }
        100% { clip-path: inset(30% 0 20% 0); transform: translate(0.125rem, -0.0625rem); }
    }

    @keyframes glitch-anim-2 {
        0% { clip-path: inset(10% 0 60% 0); transform: translate(0.125rem, -0.0625rem); }
        20% { clip-path: inset(80% 0 5% 0); transform: translate(-0.125rem, 0.125rem); }
        40% { clip-path: inset(30% 0 20% 0); transform: translate(0.0625rem, -0.125rem); }
        60% { clip-path: inset(10% 0 80% 0); transform: translate(-0.0625rem, 0.0625rem); }
        80% { clip-path: inset(50% 0 30% 0); transform: translate(0.125rem, -0.125rem); }
        100% { clip-path: inset(20% 0 70% 0); transform: translate(-0.125rem, 0.0625rem); }
    }

    /* Robot Text Animation */
    @keyframes robot-glitch-text {
        0% { opacity: 1; transform: translateX(0); text-shadow: 0 0 0.3125rem rgba(99, 102, 241, 0.8); }
        1% { opacity: 0.8; transform: translateX(0.125rem); text-shadow: 0.125rem 0 0 red; }
        2% { opacity: 1; transform: translateX(-0.125rem); text-shadow: -0.125rem 0 0 blue; }
        3% { opacity: 1; transform: translateX(0); text-shadow: 0 0 0.3125rem rgba(99, 102, 241, 0.8); }
        50% { opacity: 1; }
        51% { opacity: 0.5; transform: skewX(10deg); }
        52% { opacity: 1; transform: skewX(0deg); }
        100% { opacity: 1; }
    }

    /* --- TEXT ROTATOR FOR SUBTITLE --- */
    .hero-subtitle-container {
        position: relative;
        height: 1.875rem; /* Fixed height ~30px */
        width: 100%;
        display: flex;
        justify-content: center;
        overflow: hidden;
        margin-bottom: 2rem;
    }

    .hero-subtitle {
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-secondary);
        font-size: 0.95rem;
        letter-spacing: 0.05em;
        position: absolute;
        width: 100%;
        text-align: center;
        opacity: 0;
        animation: rotate-text 16s infinite; 
    }
    
    .hero-subtitle:nth-child(1) { animation-delay: 0s; }
    .hero-subtitle:nth-child(2) { animation-delay: 4s; }
    .hero-subtitle:nth-child(3) { animation-delay: 8s; }
    .hero-subtitle:nth-child(4) { animation-delay: 12s; }

    @keyframes rotate-text {
        0% { opacity: 0; transform: translateY(1.25rem); }
        5% { opacity: 1; transform: translateY(0); }
        25% { opacity: 1; transform: translateY(0); }
        30% { opacity: 0; transform: translateY(-1.25rem); }
        100% { opacity: 0; transform: translateY(-1.25rem); }
    }
    
    .robot-text {
        display: inline-block;
        font-weight: 700;
        color: #fff;
        animation: robot-glitch-text 4s infinite linear;
    }

    /* --- HERO CTA BUTTON (Robotic/YouTube) --- */
    .hero-btn-wrapper {
        display: flex;
        justify-content: center;
        margin-top: 1rem;
        z-index: 10;
        position: relative;
    }

    .hero-scan-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.75rem;
        background-color: #FF0000; /* FIXED: Red Background */
        color: #ffffff !important; /* FIXED: White Text */
        text-decoration: none;
        padding: 0.8rem 2rem;
        border-radius: 0.25rem; /* Slightly rounded like YT */
        font-family: 'Oswald', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        border: 1px solid #FF0000;
        box-shadow: 0 0 1.5rem rgba(255, 0, 0, 0.2);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        text-transform: uppercase;
    }

    .hero-scan-btn:hover {
        background-color: #CC0000; /* HOVER: Darker Red */
        color: #ffffff !important; /* HOVER: White Text */
        box-shadow: 0 0 2.5rem rgba(255, 0, 0, 0.7);
        transform: scale(1.05);
        border-color: #CC0000;
    }
    
    /* Active State to appear clicked */
    .hero-scan-btn:active {
        transform: scale(0.98);
    }

    .btn-icon {
        font-size: 1.2rem;
        display: flex;
        align-items: center;
    }

    /* --- TECH CARDS (OVERVIEW) --- */
    .tech-card-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(15.625rem, 1fr));
        gap: 1.25rem;
        margin-bottom: 2rem;
        position: relative;
        z-index: 1; /* Sit above the faded text */
    }
    
    .tech-card {
        background-color: #0b0d11;
        background-image: 
            linear-gradient(rgba(255, 255, 255, 0.03) 0.0625rem, transparent 0.0625rem),
            linear-gradient(90deg, rgba(255, 255, 255, 0.03) 0.0625rem, transparent 0.0625rem);
        background-size: 1.25rem 1.25rem; /* 20px */
        border: 0.0625rem solid var(--border);
        border-radius: 0.5rem;
        padding: 1.5rem;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
        box-shadow: 0 0.25rem 1.25rem rgba(0,0,0,0.4);
    }
    
    /* YOUTUBE CARD SPECIAL STYLING */
    .card-yt {
        border-color: #333;
        border-left: 0.25rem solid var(--yt-red);
        background: linear-gradient(180deg, rgba(255, 0, 0, 0.05) 0%, #0f0f0f 100%);
    }
    
    .card-yt:hover {
        box-shadow: 0 0 1.875rem rgba(255, 0, 0, 0.15) inset;
        transform: translateY(-0.1875rem);
    }
    
    /* YouTube Logo Construction in Pure CSS */
    .yt-logo-css {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2.25rem;
        height: 1.5rem;
        background-color: var(--yt-red);
        border-radius: 0.375rem;
        margin-right: 0.625rem;
        box-shadow: 0 0 0.625rem var(--yt-red);
        position: relative;
    }
    
    .yt-play-icon {
        width: 0; 
        height: 0; 
        border-top: 0.3125rem solid transparent;
        border-bottom: 0.3125rem solid transparent;
        border-left: 0.5rem solid white;
        margin-left: 0.125rem;
    }

    /* Other Cards */
    .card-cv:hover { border-color: #22d3ee; box-shadow: 0 0 1.25rem rgba(34, 211, 238, 0.15) inset; transform: translateY(-0.1875rem); }
    .card-dl:hover { border-color: #10b981; box-shadow: 0 0 1.25rem rgba(16, 185, 129, 0.15) inset; transform: translateY(-0.1875rem); }

    .card-title {
        font-family: 'Oswald', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        letter-spacing: 0.03125rem;
    }
    
    .card-desc {
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        color: var(--text-secondary);
        line-height: 1.6;
    }
    
    .card-scan-overlay {
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        background: repeating-linear-gradient(0deg, rgba(0,0,0,0.2) 0px, rgba(0,0,0,0.2) 0.0625rem, transparent 0.0625rem, transparent 0.125rem);
        pointer-events: none;
    }

    /* Highlighted Text */
    .highlight-yt {
        color: #fff;
        background: rgba(255, 0, 0, 0.2);
        padding: 0.1rem 0.3rem;
        border-radius: 0.2rem;
        border: 1px solid rgba(255, 0, 0, 0.4);
        font-weight: 600;
    }
    
    .highlight-exam {
        color: #fff;
        background: rgba(16, 185, 129, 0.2);
        padding: 0.1rem 0.3rem;
        border-radius: 0.2rem;
        border: 1px solid rgba(16, 185, 129, 0.4);
        font-weight: 600;
    }

    /* --- DEMO VISUALIZER --- */
    .demo-container {
        margin: 2rem 0;
        padding: 2rem;
        background: #080a0f;
        border: 1px solid #334155;
        border-radius: 12px;
        position: relative;
        overflow: hidden;
    }
    
    .demo-header {
        font-family: 'JetBrains Mono', monospace;
        color: #64748b;
        font-size: 0.8rem;
        margin-bottom: 2rem;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 0.5rem;
    }
    
    .demo-stage {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2rem;
        position: relative;
        z-index: 2;
    }
    
    .demo-node {
        display: flex;
        flex-direction: column;
        align-items: center;
        z-index: 2;
        width: 100px;
    }
    
    .node-icon {
        width: 60px;
        height: 60px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        background: #1e293b;
        border: 1px solid #475569;
        margin-bottom: 10px;
        box-shadow: 0 0 15px rgba(0,0,0,0.5);
    }
    
    .yt-icon { color: #ff0000; border-color: rgba(255,0,0,0.3); animation: pulse-red 2s infinite; }
    .ai-icon { color: #22d3ee; border-color: rgba(34,211,238,0.3); animation: pulse-cyan 2s infinite; }
    
    .node-label {
        font-family: 'Oswald', sans-serif;
        color: #f8fafc;
        font-size: 0.9rem;
        letter-spacing: 1px;
    }
    
    .node-status {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6rem;
        color: #64748b;
        margin-top: 4px;
    }
    
    .demo-link {
        flex: 1;
        height: 2px;
        background: #1e293b;
        position: relative;
        margin: 0 20px;
        top: -25px; /* Adjust based on icon height */
    }
    
    .data-packet {
        position: absolute;
        width: 20px;
        height: 4px;
        background: #6366f1;
        top: -1px;
        border-radius: 2px;
        box-shadow: 0 0 10px #6366f1;
        animation: flow 1.5s infinite linear;
        opacity: 0;
    }
    
    .packet-green {
        background: #10b981;
        box-shadow: 0 0 10px #10b981;
    }
    
    @keyframes flow {
        0% { left: 0%; opacity: 0; }
        10% { opacity: 1; }
        90% { opacity: 1; }
        100% { left: 100%; opacity: 0; }
    }
    
    @keyframes pulse-red { 0%, 100% { box-shadow: 0 0 0 rgba(255,0,0,0); } 50% { box-shadow: 0 0 15px rgba(255,0,0,0.3); } }
    @keyframes pulse-cyan { 0%, 100% { box-shadow: 0 0 0 rgba(34,211,238,0); } 50% { box-shadow: 0 0 15px rgba(34,211,238,0.3); } }
    
    /* Slide Stack Animation */
    .slide-stack { position: relative; width: 60px; height: 60px; margin-bottom: 10px; }
    .slide {
        position: absolute;
        width: 40px;
        height: 28px;
        background: #1e293b;
        border: 1px solid #10b981;
        border-radius: 4px;
        left: 10px;
        top: 16px;
        opacity: 0;
    }
    
    .s1 { animation: slide-pop 3s infinite; animation-delay: 0s; z-index: 1; }
    .s2 { animation: slide-pop 3s infinite; animation-delay: 1s; z-index: 2; transform: translate(5px, -5px); background: #0f1117; }
    .s3 { animation: slide-pop 3s infinite; animation-delay: 2s; z-index: 3; transform: translate(10px, -10px); background: #0f1117; }
    
    @keyframes slide-pop {
        0% { opacity: 0; transform: translateY(10px) scale(0.9); }
        20% { opacity: 1; transform: translateY(0) scale(1); }
        80% { opacity: 1; }
        100% { opacity: 0; }
    }
    
    .demo-terminal {
        background: #000;
        padding: 1rem;
        border-radius: 6px;
        border-left: 2px solid #6366f1;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        color: #4ade80;
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    .term-line { opacity: 0.8; }

    /* --- INPUTS --- */
    .stTextInput input {
        background-color: var(--bg-card) !important;
        border: 0.0625rem solid var(--border) !important;
        color: var(--text-primary) !important;
        border-radius: var(--radius-md);
        padding: 0.75rem 1rem;
        font-size: 0.9375rem;
        transition: all 0.2s ease;
    }
    
    .stTextInput input:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 0.0625rem var(--accent-primary), 0 0 0.9375rem var(--accent-glow) !important;
    }

    /* --- BUTTONS --- */
    div.stButton > button {
        background-color: var(--bg-surface);
        border: 0.0625rem solid var(--border);
        color: var(--text-primary);
        border-radius: var(--radius-sm);
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    div.stButton > button:hover {
        background-color: var(--border);
        border-color: var(--text-secondary);
    }
    
    button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        border: none !important;
        color: white !important;
        font-weight: 600;
        box-shadow: 0 0.25rem 0.75rem rgba(99, 102, 241, 0.3);
    }
    
    button[kind="primary"]:hover {
        box-shadow: 0 0.375rem 1.25rem rgba(99, 102, 241, 0.5);
        transform: translateY(-0.0625rem);
    }
    
    /* SPECIAL SCAN BUTTON STYLE */
    button[kind="secondary"] {
        background-color: #000 !important;
        border: 1px solid var(--yt-red) !important;
        color: var(--yt-red) !important;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 1px;
        text-transform: uppercase;
        box-shadow: 0 0 10px rgba(255, 0, 0, 0.2) !important;
    }
    button[kind="secondary"]:hover {
        background-color: var(--yt-red) !important;
        color: #fff !important;
        box-shadow: 0 0 20px rgba(255, 0, 0, 0.5) !important;
    }

    /* --- CONSOLE OUTPUT --- */
    .console-box {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8125rem;
        background: #000000;
        border: 0.0625rem solid #333;
        border-left: 0.1875rem solid var(--success);
        border-radius: var(--radius-sm);
        padding: 0.875rem;
        color: #4ade80; /* Terminal Green */
        display: flex;
        align-items: center;
        gap: 0.75rem;
        box-shadow: inset 0 0 1.25rem rgba(0,0,0,0.5);
    }
    
    .blink { animation: blinker 1s step-end infinite; }
    @keyframes blinker { 50% { opacity: 0; } }

    /* --- GENERAL UI --- */
    .section-header {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-secondary);
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    
    .section-header::after {
        content: ""; flex: 1; height: 0.0625rem;
        background: linear-gradient(90deg, var(--border), transparent);
    }
    
    /* UNIVERSAL IMAGE STYLING (Applies to all st.image calls) */
    div[data-testid="stImage"] {
        border-radius: var(--radius-md);
        overflow: hidden;
    }
    
    div[data-testid="stImage"] img {
        border-radius: var(--radius-md);
        transition: transform 0.3s ease;
    }
    
    div[data-testid="stImage"]:hover img {
        transform: scale(1.02);
    }
    
    div[data-testid="stImageCaption"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6875rem;
        color: var(--text-secondary);
        background: transparent;
        padding-top: 0.5rem;
    }
    
    /* --- EXPANDER CUSTOMIZATION --- */
    .streamlit-expanderHeader {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem !important;
        border: 0.0625rem solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
    }
    .streamlit-expanderContent {
        border: 0.0625rem solid var(--border);
        border-top: none;
        border-bottom-left-radius: var(--radius-sm);
        border-bottom-right-radius: var(--radius-sm);
        background-color: var(--bg-depth);
        padding: 1.25rem;
    }
    
    /* --- SETUP PROTOCOL STYLING (TARGETED CONTAINER) --- */
    div[data-testid="stVerticalBlock"]:has(div.setup-wizard-marker) {
        background-color: transparent; /* Clean background */
        border: none; /* Border removed */
        box-shadow: 0 0 3.125rem rgba(0,0,0,0.5) inset;
        border-radius: var(--radius-md);
        padding: 2rem;
        margin-top: 1.5rem; /* Distinct separation from Hero */
        position: relative;
        overflow: hidden;
        animation: slideDown 0.6s cubic-bezier(0.2, 0.8, 0.2, 1);
    }
    
    /* SETUP WIZARD IMAGE SPECIFICS */
    div[data-testid="stVerticalBlock"]:has(div.setup-wizard-marker) div[data-testid="stImage"] {
        border: 0.125rem solid var(--border);
        box-shadow: 0 0.25rem 1rem rgba(0,0,0,0.5);
    }
    
    div[data-testid="stVerticalBlock"]:has(div.setup-wizard-marker) div[data-testid="stImage"]:hover {
        border-color: var(--accent-primary);
        box-shadow: 0 0 1.25rem rgba(99, 102, 241, 0.4);
    }

    div[data-testid="stVerticalBlock"]:has(div.setup-wizard-marker) div[data-testid="stImage"]:hover img {
        transform: scale(1.15) !important;
    }
    
    /* Hide markers */
    .setup-wizard-marker, .input-console-marker { display: none; }
    
    /* INPUT CONSOLE STYLING */
    div[data-testid="stVerticalBlock"]:has(div.input-console-marker) {
        background-color: transparent;
        border: 1px solid var(--border);
        border-left: 4px solid var(--yt-red); /* Robotic accent */
        border-radius: 4px; /* Sharper corners */
        padding: 1.5rem;
        box-shadow: 0 0 20px rgba(0,0,0,0.5) inset;
        margin-bottom: 2rem;
        position: relative;
    }
    
    .step-header {
        font-family: 'JetBrains Mono', monospace;
        color: var(--yt-red);
        border-bottom: 1px solid var(--border);
        padding-bottom: 10px;
        margin-bottom: 20px;
        font-size: 0.9rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .stepper-dots {
        display: flex;
        justify-content: center;
        gap: 12px;
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid var(--border);
    }
    
    .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--border);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .dot.active {
        background: var(--yt-red);
        box-shadow: 0 0 10px var(--yt-red);
        transform: scale(1.3);
    }
    
    @keyframes slideDown { 
        from { opacity: 0; transform: translateY(-10px); } 
        to { opacity: 1; transform: translateY(0); } 
    }
</style>
""", unsafe_allow_html=True)

# --- HELPERS ---
def get_video_info(url, cookies=None, proxy=None):
    opts = {
        'quiet': True, 
        'nocheckcertificate': True, 
        'user_agent': 'Mozilla/5.0',
        'noplaylist': True # Prevent playlist processing
    }
    if cookies: opts['cookiefile'] = cookies
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False), None
    except Exception as e:
        return None, str(e)

def create_pdf(buffers):
    if not buffers: return None
    path = os.path.join(tempfile.gettempdir(), "lecture_export.pdf")
    imgs = []
    for b in buffers:
        i = cv2.imdecode(b, cv2.IMREAD_COLOR)
        if i is not None: imgs.append(Image.fromarray(cv2.cvtColor(i, cv2.COLOR_BGR2RGB)))
    if imgs:
        imgs[0].save(path, "PDF", resolution=100.0, save_all=True, append_images=imgs[1:])
        return path
    return None

def fmt(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02}"

# --- HEADER ---
st.markdown("""
<div class="hero-container">
<div class="scan-line"></div>
<div class="hero-title" data-text="LECTURENOTES_PRO">LECTURENOTES_PRO</div>
<br>
<div class="hero-subtitle-container">
<div class="hero-subtitle">>> INITIALIZING <span class="robot-text">INTELLIGENT VIDEO PARSER v1.0</span>...</div>
<div class="hero-subtitle">>> DETECTING SIGNIFICANT VISUAL CHANGES IN LECTURE STREAMS...</div>
<div class="hero-subtitle">>> GENERATING EXAM-READY STUDY MATERIAL AUTOMATICALLY...</div>
<div class="hero-subtitle">>> OPTIMIZING CONTENT FOR RAPID KNOWLEDGE INGESTION...</div>
</div>
<div class="hero-btn-wrapper">
<a href="?setup=true#setup_location" class="hero-scan-btn" target="_self">
<span class="btn-icon">▶</span> SCAN_LECTURE // INITIATE_SETUP
</a>
</div>
</div>
""", unsafe_allow_html=True)

# --- SETUP PROTOCOL WIZARD (SEPARATE BLOCK) ---
if st.session_state.get('setup_active', False): 
    # Anchor for scroll
    st.markdown('<div id="setup_location"></div>', unsafe_allow_html=True)
    
    if 'setup_step' not in st.session_state:
        st.session_state.setup_step = 1
    
    step = st.session_state.setup_step
    
    # Placeholder Logic for Images
    def get_step_image(step_num):
        fname = f"step_0{step_num}.jpg"
        if os.path.exists(fname): return fname
        return None

    # Distinct Container Targeted by CSS
    with st.container():
        st.markdown('<div class="setup-wizard-marker"></div>', unsafe_allow_html=True)
        
        # --- NEW HEADER STYLE FOR SETUP WIZARD ---
        st.markdown("""
        <div style="text-align:center; margin-bottom: 2rem;">
            <div style="display:flex; justify-content:center; gap:8px; margin-bottom:5px; opacity:0.6;">
                <div style="width:12px; height:12px; background:var(--text-secondary); border-radius:2px;"></div>
                <div style="width:12px; height:12px; background:var(--text-secondary); border-radius:2px;"></div>
                <div style="width:12px; height:12px; background:var(--text-secondary); border-radius:2px;"></div>
            </div>
            <div style="font-family:'JetBrains Mono', monospace; font-size: 3.5rem; font-weight:800; color:var(--text-secondary); letter-spacing: -2px; text-transform:uppercase;">
                <span style="opacity:0.5;">SETUP EASILY AND USE</span> <span style="background: linear-gradient(to bottom, #ff0000, #000000); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 4.5rem;">FREE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Header (Dynamic Status based on STEP)
        status_map = {
            1: "INSTALLING_BRIDGE",
            2: "VERIFYING_SESSION",
            3: "INITIATING_EXTRACT",
            4: "EXPORTING_TOKEN",
            5: "AWAITING_UPLOAD",
            6: "TARGET_ACQUISITION"
        }
        
        is_verified = st.session_state.get('cookies_path') is not None
        status_text = "AUTH_VERIFIED" if is_verified else status_map.get(step, "PROCESSING")
        status_color = "#10b981" if is_verified else "#ef4444" 
        
        st.markdown(f"""
            <div class="step-header">
                <span>>> SETUP_PROTOCOL // PHASE_{step:02d}</span>
                <span style="color:{status_color}">STATUS: {status_text}</span>
            </div>
        """, unsafe_allow_html=True)
        
        # Content Layout
        # Steps 1-5 use split columns, Step 6 uses full width logic
        
        if step < 6:
            c_text, c_img = st.columns([1, 1], gap="medium")
            with c_text:
                if step == 1:
                    st.info("⚠️ **ACTION REQUIRED**")
                    st.markdown("""
                        **1. Install Authentication Bridge**
                        To access restricted content, the system requires a verified session token.
                        Download **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc?pli=1)**.
                    """)
                elif step == 2:
                    st.info("🔐 **VERIFY SESSION**")
                    st.markdown("""
                        **2. Open Target Source**
                        Open **YouTube.com** in a new browser tab and ensure you are **Signed In**.
                        **3. Access Extensions**
                        Click the **Extensions Puzzle Piece** icon in Chrome.
                    """)
                elif step == 3:
                    st.info("🖱️ **SELECT EXTRACTOR**")
                    st.markdown("""
                        **4. Initialize Extraction**
                        Click **'Get cookies.txt LOCALLY'** from your extensions list to prepare session data.
                    """)
                elif step == 4:
                    st.info("⬇️ **EXPORT CREDENTIALS**")
                    st.markdown("""
                        **5. Download Session Token**
                        Click the **Blue 'Export' Button** in the extension popup to get the `.txt` file.
                    """)
                elif step == 5:
                    st.success("✅ **UPLOAD VERIFICATION**")
                    st.markdown("**6. Authorize System**\nUpload `www.youtube.com_cookies.txt` below.")
                    uploaded_cookie = st.file_uploader("UPLOAD COOKIES.TXT", type=['txt'], label_visibility="collapsed")
                    if uploaded_cookie:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='wb') as fp:
                            fp.write(uploaded_cookie.getvalue())
                            st.session_state['cookies_path'] = fp.name
                        st.rerun()

            with c_img:
                img_path = get_step_image(step)
                st.markdown('<div class="step-image-container">', unsafe_allow_html=True)
                if img_path:
                    st.image(img_path, use_container_width=True)
                else:
                    st.code(f"[SYSTEM_ERR: VISUAL_GUIDE_MISSING]\nLoading: step_0{step}.jpg...", language="bash")
                st.markdown('</div>', unsafe_allow_html=True)
        
        else:
            # --- STEP 6: INTEGRATED SCANNING (REPLACES BOTTOM LOGIC) ---
            st.info("🎯 **TARGET ACQUISITION & EXECUTION**")
            st.markdown("Enter URL, Resolve Metadata, and **Execute Extraction Sequence** immediately.")
            
            # Embedded Input Console Styling
            st.markdown('<div class="input-console-marker"></div>', unsafe_allow_html=True)
            
            # Input Row
            col_in, col_btn = st.columns([3, 1])
            with col_in:
                url_wiz = st.text_input("INPUT SOURCE", value=st.session_state['url_input'], placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed", key="wiz_url")
            with col_btn:
                if st.button("ANALYZE SOURCE", type="primary", use_container_width=True):
                    if not url_wiz:
                        st.warning("Target URL required.")
                    else:
                        st.session_state['url_input'] = url_wiz
                        st.session_state['scan_complete'] = False # Reset scan status
                        info, err = get_video_info(url_wiz, cookies=st.session_state.get('cookies_path'))
                        if info:
                            st.session_state['video_info'] = info
                        else:
                            st.error(f"TARGET LOCK FAILED: {err}")

            # If Video Info is loaded, show controls and Scan Button
            if st.session_state['video_info']:
                meta = st.session_state['video_info']
                st.success(f"LOCKED: {meta.get('title')[:60]}...")
                
                # Configuration Area (Sliders)
                with st.expander("SCAN CONFIGURATION", expanded=True):
                    # Quality & Time
                    c_conf1, c_conf2 = st.columns(2)
                    with c_conf1:
                        st.markdown("**STREAM PARAMETERS**")
                        # Format Logic
                        fmts = [f for f in meta.get('formats', []) if f.get('height')]
                        heights = sorted(list(set(f['height'] for f in fmts)), reverse=True)
                        q_map = {f"{h}p RAW": f"bestvideo[height<={h}]/best[height<={h}]" for h in heights}
                        q_map["AUTO_NEGOTIATE"] = "bestvideo/best"
                        qual = st.selectbox("QUALITY STREAM", list(q_map.keys()), label_visibility="collapsed")
                    
                    with c_conf2:
                        st.markdown("**TEMPORAL WINDOW**")
                        duration = meta.get('duration') or 0
                        if duration <= 0: duration = 100
                        start_t, end_t = st.slider("PROCESS WINDOW", 0, duration, (0, duration), label_visibility="collapsed")

                    st.markdown("---")
                    c_adv1, c_adv2 = st.columns(2)
                    with c_adv1:
                        st.caption("VISUAL THRESHOLDS")
                        st.slider("Pixel Delta", 10, 100, key='sensitivity')
                    with c_adv2:
                        st.caption("SKIP RATE (Sec)")
                        st.slider("Max Skip", 5, 60, key='max_skip')

                # EXECUTION BUTTON
                if st.button("INITIATE EXTRACTION SEQUENCE", type="secondary", use_container_width=True):
                    # --- SCANNIN LOGIC MOVED HERE ---
                    st.session_state['captured_images'] = []
                    
                    console_ph = st.empty()
                    console_ph.markdown('<div class="console-box"><span class="blink">_</span> ALLOCATING BUFFER...</div>', unsafe_allow_html=True)
                    prog_bar = st.progress(0)
                    
                    ydl_opts = {
                        'format': q_map[qual], 
                        'quiet': True, 
                        'nocheckcertificate': True,
                        'noplaylist': True,
                        'cookiefile': st.session_state.get('cookies_path') 
                    }
                    
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            stream_link = ydl.extract_info(url_wiz, download=False).get('url')
                            
                        if stream_link:
                            console_ph.markdown(f'<div class="console-box"><span class="blink">●</span> STREAM LOCKED. SEEKING: {fmt(start_t)}</div>', unsafe_allow_html=True)
                            
                            cap = cv2.VideoCapture(stream_link, cv2.CAP_FFMPEG)
                            if cap.isOpened():
                                fps = cap.get(cv2.CAP_PROP_FPS) or 30
                                cap.set(cv2.CAP_PROP_POS_MSEC, start_t * 1000)
                                
                                last = None
                                curr = int(start_t * fps)
                                end = int(end_t * fps)
                                total = max(1, end - curr)
                                origin = curr
                                
                                sensitivity = st.session_state['sensitivity']
                                strictness = st.session_state['strictness']
                                min_skip = st.session_state['min_skip']
                                max_skip = st.session_state['max_skip']
                                
                                while curr < end:
                                    cap.set(cv2.CAP_PROP_POS_FRAMES, curr)
                                    ret, frame = cap.read()
                                    if not ret: break
                                    
                                    # Update metrics
                                    p = (curr - origin) / total
                                    prog_bar.progress(min(max(p, 0.0), 1.0))
                                    ts = fmt(curr / fps)
                                    console_ph.markdown(f'<div class="console-box"><span class="blink">●</span> PROCESSING: {ts} | BUFFER: OK</div>', unsafe_allow_html=True)
                                    
                                    # CV Logic
                                    small = cv2.resize(frame, (640, 360))
                                    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                                    gray = cv2.GaussianBlur(gray, (21, 21), 0)
                                    
                                    is_diff = False
                                    if last is None:
                                        is_diff = True
                                        last = gray
                                    else:
                                        d = cv2.absdiff(last, gray)
                                        _, th = cv2.threshold(d, sensitivity, 255, cv2.THRESH_BINARY)
                                        if np.sum(th) > (640 * 360 * (strictness/100) * 255):
                                            is_diff = True
                                            last = gray
                                    
                                    if is_diff:
                                        _, b = cv2.imencode('.jpg', frame)
                                        st.session_state['captured_images'].append(b)
                                        st.toast(f"Event Logged: {ts}")
                                        curr += int(fps * max_skip)
                                    else:
                                        curr += int(fps * min_skip)
                                
                                cap.release()
                                prog_bar.progress(1.0)
                                st.session_state['scan_complete'] = True # MARK COMPLETED
                                console_ph.markdown('<div class="console-box" style="color:#10b981; border-color:#10b981;">✓ SEQUENCE COMPLETE</div>', unsafe_allow_html=True)
                                st.rerun() # Refresh to show results button
                            else:
                                st.error("STREAM HANDSHAKE FAILED")
                    except Exception as e:
                        st.error(f"Error during scan: {str(e)}")

            # RESULT ACTION
            if st.session_state.get('scan_complete') and st.session_state['captured_images']:
                st.success(f"SCAN SUCCESSFUL. {len(st.session_state['captured_images'])} Slides Captured.")
                if st.button("FINISH & VIEW GALLERY >>", type="primary", use_container_width=True):
                    st.session_state['setup_active'] = False
                    st.rerun()

        # Navigation Footer
        st.write("")
        c_nav1, c_nav2, c_nav3 = st.columns([1, 4, 1])
        
        with c_nav1:
            if step > 1:
                if st.button("<< PREV"):
                    st.session_state.setup_step -= 1
                    st.rerun()
        
        with c_nav2:
            dots_html = "".join([f'<div class="dot {"active" if i+1 == step else ""}">{""}</div>' for i in range(6)])
            st.markdown(f'<div class="stepper-dots">{dots_html}</div>', unsafe_allow_html=True)
            
        with c_nav3:
            if step < 6: # Standard Next for steps 1-5
                if st.button("NEXT >>"):
                    st.session_state.setup_step += 1
                    st.rerun()

st.divider()

# --- VISUAL DEMONSTRATION SECTION ---
st.markdown("""
<div class="demo-container">
<div class="demo-header">>> LIVE_DEMONSTRATION // NEURAL_PROCESSING_VISUALIZER</div>
<div class="demo-stage">
<!-- STAGE 1: RAW STREAM -->
<div class="demo-node">
<div class="node-icon yt-icon">▶</div>
<div class="node-label">RAW_STREAM</div>
<div class="node-status">BUFFERING...</div>
</div>
<!-- CONNECTION 1 -->
<div class="demo-link">
<div class="data-packet"></div>
<div class="data-packet" style="animation-delay: 0.5s"></div>
<div class="data-packet" style="animation-delay: 1.0s"></div>
</div>
<!-- STAGE 2: AI FILTER -->
<div class="demo-node">
<div class="node-icon ai-icon">⌾</div>
<div class="node-label">SCAN</div>
<div class="node-status" style="color:#22d3ee;">ANALYZING</div>
</div>
<!-- CONNECTION 2 -->
<div class="demo-link">
<div class="data-packet packet-green"></div>
<div class="data-packet packet-green" style="animation-delay: 0.6s"></div>
</div>
<!-- STAGE 3: SLIDES -->
<div class="demo-node">
<div class="slide-stack">
<div class="slide s1"></div>
<div class="slide s2"></div>
<div class="slide s3"></div>
</div>
<div class="node-label">SMART_DECK</div>
<div class="node-status" style="color:#10b981;">OPTIMIZED</div>
</div>
</div>
<div class="demo-terminal">
<span class="term-line">> INGESTING_FRAME_BUFFER...</span>
<span class="term-line">> DETECTING_REDUNDANCY... [SKIP]</span>
<span class="term-line">> DETECTING_UNIQUE_CONTENT... [CAPTURE]</span>
<span class="term-line blink">> COMPILING_ESSENTIAL_KNOWLEDGE...</span>
</div>
</div>
""", unsafe_allow_html=True)

# --- ROBOTIC SYSTEM OVERVIEW ---
st.markdown("""
<div style="text-align:center; margin-bottom: 2rem; margin-top: 3rem;">
    <div style="display:flex; justify-content:center; gap:8px; margin-bottom:5px; opacity:0.6;">
        <div style="width:12px; height:12px; background:var(--text-secondary); border-radius:2px;"></div>
        <div style="width:12px; height:12px; background:var(--text-secondary); border-radius:2px;"></div>
        <div style="width:12px; height:12px; background:var(--text-secondary); border-radius:2px;"></div>
    </div>
    <div style="font-family:'JetBrains Mono', monospace; font-size: 4.5rem; font-weight:800; color:var(--border); opacity:0.25; letter-spacing: -2px; -webkit-mask-image: linear-gradient(to bottom, black 50%, transparent 100%); mask-image: linear-gradient(to bottom, black 50%, transparent 100%);">
        SYSTEM ARCHITECTURE
    </div>
</div>
""", unsafe_allow_html=True)

# Cards
st.markdown("""
<div class="tech-card-container">
<div class="tech-card card-yt">
<div class="card-scan-overlay"></div>
<div class="card-title">
<div class="yt-logo-css"><div class="yt-play-icon"></div></div>
<span style="color:#fff;">LECTURE_FEED_INGEST</span>
</div>
<div class="card-desc">
Feed the system any <span class="highlight-yt">YouTube Lecture URL</span>. The parser establishes a direct data pipe to the source, bypassing standard playback to access raw visual data.
</div>
</div>
<div class="tech-card card-cv">
<div class="card-scan-overlay"></div>
<div class="card-title" style="color: #22d3ee;">
<span style="font-size:1.2rem; margin-right:0.625rem;">⌾</span> SCAN
</div>
<div class="card-desc">
<strong>Neural Scan Active.</strong> The algorithm compares consecutive scenes to detect significant visual changes (blackboard updates, new slides), filtering out noise and instructor movement.
</div>
</div>
<div class="tech-card card-dl">
<div class="card-scan-overlay"></div>
<div class="card-title" style="color: #10b981;">
<span style="font-size:1.2rem; margin-right:0.625rem;">🎓</span> RAPID_REVIEW_ARTIFACT
</div>
<div class="card-desc">
<span class="highlight-exam">Exam Mode Enabled.</span> Essential visual data is captured and compiled into a streamlined PDF. Perfect for one-night-before study sessions and last-minute revision.
</div>
</div>
</div>
""", unsafe_allow_html=True)

st.write("") 

# --- MAIN WORKSPACE (RESULTS GALLERY ONLY) ---
# NOTE: All scanning logic moved to Step 06 above. This section now only handles display of results.
if not st.session_state['setup_active']:
    
    # If we have results, show them
    if st.session_state['captured_images']:
        st.markdown('<div class="section-header">SLIDE GALLERY</div>', unsafe_allow_html=True)
        
        # Actions Row
        c_act1, c_act2 = st.columns([1, 4])
        with c_act1:
            # New Scan Button
            if st.button("NEW SCAN", type="secondary", use_container_width=True):
                st.session_state['setup_active'] = True
                st.session_state['setup_step'] = 1
                st.session_state['scan_complete'] = False
                st.session_state['captured_images'] = []
                st.rerun()
        with c_act2:
             # PDF Download
            pdf = create_pdf(st.session_state['captured_images'])
            if pdf and os.path.exists(pdf):
                with open(pdf, "rb") as f:
                    st.download_button("DOWNLOAD FULL PDF REPORT", f.read(), "lecture_notes.pdf", "application/pdf", type="primary", use_container_width=True)

        st.write("")
        st.markdown(f'<div class="section-header">CAPTURED ARTIFACTS ({len(st.session_state["captured_images"])})</div>', unsafe_allow_html=True)
        
        cols = st.columns(3)
        for i, buf in enumerate(st.session_state['captured_images']):
            im = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            with cols[i % 3]:
                st.image(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), caption=f"ID_{i:03d}", use_container_width=True)
    
    else:
        # Fallback if user somehow exits wizard without scanning
        st.info("No artifacts available. Initialize a scan to begin.")
        if st.button("OPEN SCANNER"):
            st.session_state['setup_active'] = True
            st.session_state['setup_step'] = 1
            st.rerun()

# --- MAIN APP LOGIC END ---
