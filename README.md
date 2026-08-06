\# NovaDL



\[!\[Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)

\[!\[License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)



NovaDL is a command-line media downloader built on top of yt-dlp and spotdl, providing automatic dependency management, metadata tagging and playlist processing. It automates the downloading and metadata tagging of media from supported platforms, handling dependencies and fallback mechanisms automatically.



\## Features



\* \*\*Multithreaded Playlist Processing:\*\* Downloads multiple items from playlists or albums concurrently using `ThreadPoolExecutor` to reduce overall processing time.

\* \*\*Self-Bootstrapping Environment:\*\* Automatically downloads necessary portable binaries (`yt-dlp`, Deno) and updates required Python packages (`spotdl`) in an isolated `tools/` directory, minimizing manual setup.

\* \*\*Fallback Mechanisms:\*\* Automatically switches to alternative extraction clients or methods if the primary request fails.

\* \*\*Aria2c Integration:\*\* Attempts to install and utilize `aria2c` as an external downloader for concurrent file fragment downloading.

\* \*\*Interactive CLI:\*\* Provides a minimal, console-based interface for selecting formats (MP3, WAV, MP4) and managing download directories.



\## Supported Platforms



\* YouTube

\* Spotify

\* SoundCloud



\## Prerequisites



\* \*\*OS:\*\* Windows 10/11 (fully automated dependency management). Operates on Linux/macOS assuming `yt-dlp`, `deno`, and `ffmpeg` are available in the system PATH.

\* \*\*Python:\*\* Version 3.8 or higher.

\* \*\*FFmpeg:\*\* Required for media merging and conversion. On Windows, the script looks for FFmpeg in standard `winget` installation paths. If not found, install it via: `winget install ffmpeg`.



\## Usage



Clone the repository and run the script directly. No prior `pip install` is required, as the script handles its own dependencies.



```bash

git clone https://github.com/yourusername/NovaDL.git

cd NovaDL

python novadl.py

