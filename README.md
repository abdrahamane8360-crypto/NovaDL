# NovaDL

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT">
</p>

NovaDL is a powerful command-line media downloader built on top of `yt-dlp` and `spotdl`. It automates the downloading, metadata tagging, and playlist processing from multiple platforms while handling dependencies and fallback mechanisms completely automatically.

---

## 🚀 Features

⚡ Multithreaded Processing: Downloads multiple items from playlists or albums concurrently using `ThreadPoolExecutor` to drastically reduce processing time.

📦 Self-Bootstrapping Environment: Automatically downloads necessary portable binaries (`yt-dlp`, `Deno`) and updates Python packages (`spotdl`) in an isolated `tools/` directory, minimizing manual setup.

🔄 Fallback Mechanisms: Automatically switches to alternative extraction clients or methods if the primary request fails.

🌐 Aria2c Integration: Detects and utilizes `aria2c` as an external downloader for high-speed concurrent file fragment downloading.

💻 Interactive CLI: Provides a minimal, intuitive console-based interface for selecting formats (MP3, WAV, MP4) and managing download directories.

---

## 🎵 Supported Platforms

📹 YouTube (Videos, Playlists, Audio)

🎧 Spotify (Tracks, Albums, Playlists)

☁️ SoundCloud (Tracks, Sets)

---

## 🛠️ Prerequisites

💻 OS: Windows 10/11 (fully automated dependency management). Linux/macOS are supported if `yt-dlp`, `deno`, and `ffmpeg` are already available in your system PATH.

🐍 Python: Version 3.8 or higher.

🎬 FFmpeg: Required for media merging and conversion. On Windows, NovaDL automatically checks standard `winget` installation paths. If missing, install it via:
```bash
winget install ffmpeg


💻 Usage
git clone [https://github.com/W3rzzzy/NovaDL.git](https://github.com/W3rzzzy/NovaDL.git) && cd NovaDL && python NovaDL.py