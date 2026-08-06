import os
import sys
import subprocess
import re
import io
import zipfile
import urllib.request
from urllib.parse import urlparse, parse_qs
import json
import time
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor

if os.name == 'nt':
    import msvcrt
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.system('')

# Директория для портативных зависимостей (yt-dlp, deno).
# Позволяет избежать проблем с установкой через pip и отсутствием MSVC на Windows.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
YTDLP_EXE = os.path.join(TOOLS_DIR, "yt-dlp.exe")
DENO_EXE = os.path.join(TOOLS_DIR, "deno.exe")
CONFIG_FILE = os.path.join(TOOLS_DIR, "config.json")

def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(cfg):
    try:
        os.makedirs(TOOLS_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

_config = _load_config()

USER_HOME = os.path.expanduser("~")
SAVE_PATH = os.environ.get("NOVADL_SAVE_PATH") or _config.get("save_path") or os.path.join(USER_HOME, "Downloads", "NovaDL")
COOKIES_PATH = os.environ.get("NOVADL_COOKIES_PATH", os.path.join(USER_HOME, "Downloads", "cookies.txt"))
FFMPEG_DIR = os.environ.get(
    "NOVADL_FFMPEG_DIR",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe", "ffmpeg-8.1.2-full_build", "bin")
)

if FFMPEG_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

if not os.path.isdir(FFMPEG_DIR):
    print(f"[-] Внимание: папка FFmpeg не найдена по пути {FFMPEG_DIR}")
    print("[-] Проверьте NOVADL_FFMPEG_DIR или переустановите FFmpeg.")

YTDLP_RELEASE_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
DENO_RELEASE_URL = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"

UPDATE_STATE_FILE = os.path.join(TOOLS_DIR, "update_state.json")
UPDATE_INTERVAL_SECONDS = 12 * 60 * 60

CLR = "\033[0m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
BOLD = "\033[1m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def ensure_save_directory():
    if not os.path.exists(SAVE_PATH):
        os.makedirs(SAVE_PATH)
    return SAVE_PATH

def prompt_change_save_directory():
    global SAVE_PATH
    print(f"\n{WHITE}Текущая директория:{CLR} {YELLOW}{SAVE_PATH}{CLR}")
    new_path = input(f"{WHITE}Новая директория (Enter - отмена):{CLR} ").strip().strip('"')
    if not new_path:
        print(f"{YELLOW}[~] Операция отменена.{CLR}")
        return

    try:
        os.makedirs(new_path, exist_ok=True)
    except Exception as e:
        print(f"{RED}[-] Не удалось использовать данную директорию: {e}{CLR}")
        return

    if os.environ.get("NOVADL_SAVE_PATH"):
        print(f"{YELLOW}[~] Внимание: переменная окружения NOVADL_SAVE_PATH переопределит эту настройку при следующем запуске.{CLR}")

    SAVE_PATH = new_path
    cfg = _load_config()
    cfg["save_path"] = new_path
    if _save_config(cfg):
        print(f"{GREEN}[+] Директория сохранена:{CLR} {WHITE}{new_path}{CLR}")
    else:
        print(f"{YELLOW}[~] Директория изменена только для текущей сессии (сбой сохранения конфига).{CLR}")

def _with_retries(fn, attempts=3, delay=2):
    last_err = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(delay)
    raise last_err

def ensure_ytdlp():
    if os.name != 'nt':
        return "yt-dlp"

    if os.path.exists(YTDLP_EXE):
        return YTDLP_EXE

    os.makedirs(TOOLS_DIR, exist_ok=True)
    print(f"{CYAN}[*] Загрузка портативной версии yt-dlp...{CLR}")
    try:
        _with_retries(lambda: urllib.request.urlretrieve(YTDLP_RELEASE_URL, YTDLP_EXE))
        return YTDLP_EXE
    except Exception as e:
        print(f"{RED}[-] Ошибка загрузки yt-dlp: {e}{CLR}")
        print(f"{YELLOW}[~] Попытка использовать системный yt-dlp из PATH.{CLR}")
        return "yt-dlp"

def ensure_deno():
    """Deno требуется yt-dlp как JS-runtime для прохождения защиты YouTube."""
    if os.name != 'nt':
        return

    if os.path.exists(DENO_EXE):
        if TOOLS_DIR not in os.environ.get("PATH", ""):
            os.environ["PATH"] = TOOLS_DIR + os.pathsep + os.environ.get("PATH", "")
        return

    os.makedirs(TOOLS_DIR, exist_ok=True)
    print(f"{CYAN}[*] Загрузка Deno (JS-runtime)...{CLR}")
    try:
        def _fetch():
            with urllib.request.urlopen(DENO_RELEASE_URL, timeout=30) as resp:
                return resp.read()
        zip_bytes = _with_retries(_fetch)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extract("deno.exe", TOOLS_DIR)
        os.environ["PATH"] = TOOLS_DIR + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        print(f"{RED}[-] Ошибка загрузки Deno: {e}{CLR}")
        print(f"{YELLOW}[~] Без JS-runtime возможны ошибки 'Requested format is not available'.{CLR}")

_UPDATE_STATE_LOCK = threading.Lock()

def check_should_update(state, key):
    last = state.get(key, 0)
    return (time.time() - last) > UPDATE_INTERVAL_SECONDS

def update_tools(ytdlp_bin):
    with _UPDATE_STATE_LOCK:
        state = load_update_state()
        if not check_should_update(state, "ytdlp"):
            return
        state["ytdlp"] = time.time()
        save_update_state(state)
        
    print(f"{CYAN}[*] Проверка обновлений yt-dlp...{CLR}")
    try:
        subprocess.run([ytdlp_bin, "-U"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
    except Exception:
        pass

def ensure_spotdl_dependencies():
    """Обновление зависимостей spotdl без тяжелых пакетов, требующих компилятор C++ на Windows."""
    with _UPDATE_STATE_LOCK:
        state = load_update_state()
        if not check_should_update(state, "spotdl_deps"):
            return
        state["spotdl_deps"] = time.time()
        save_update_state(state)
        
    print(f"{CYAN}[*] Проверка зависимостей spotdl...{CLR}")
    for pkg in ("yt-dlp", "yt-dlp-ejs", "spotdl"):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "--no-input", pkg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45
            )
        except Exception:
            pass

CONCURRENT_FRAGMENTS = int(os.environ.get("NOVADL_CONCURRENT_FRAGMENTS", "16"))
SPOTDL_THREADS = os.environ.get("NOVADL_SPOTDL_THREADS", "16")
HTTP_CHUNK_SIZE = os.environ.get("NOVADL_HTTP_CHUNK_SIZE", "10M")
PLAYLIST_WORKERS = max(1, int(os.environ.get("NOVADL_PLAYLIST_WORKERS", "3")))

_ARIA2C_PATH = shutil.which("aria2c")

def ensure_aria2c_background():
    global _ARIA2C_PATH
    if os.name != 'nt' or _ARIA2C_PATH or not shutil.which("winget"):
        return
    try:
        subprocess.run(
            ["winget", "install", "--id", "aria2.aria2", "-e", "--silent",
             "--accept-package-agreements", "--accept-source-agreements"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45
        )
        _ARIA2C_PATH = shutil.which("aria2c")
    except Exception:
        pass

def get_speed_args():
    if _ARIA2C_PATH:
        return [
            "--downloader", "aria2c",
            "--downloader-args", f"aria2c:-x 16 -s 16 -k 1M",
        ]
    return [
        "--concurrent-fragments", str(CONCURRENT_FRAGMENTS),
        "--http-chunk-size", HTTP_CHUNK_SIZE,
    ]

def clean_url(url):
    url = url.strip()
    if "spotify.com" in url and "?" in url:
        url = url.split("?")[0]
    return url

def get_platform(url):
    url = url.strip()
    if re.search(r'(spotify\.com)', url, re.IGNORECASE): return "Spotify"
    if re.search(r'(youtube\.com|youtu\.be)', url, re.IGNORECASE): return "YouTube"
    if re.search(r'(soundcloud\.com)', url, re.IGNORECASE): return "SoundCloud"
    return None

def is_playlist_url(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    
    qs = parse_qs(parsed.query)
    if "list" in qs:
        if "v" in qs:
            return False
        return True
        
    path = parsed.path.lower()
    return any(seg in path for seg in ("/sets/", "/playlist", "/album", "/sets"))

def render_progress_bar(percentage, status_text, speed_text=""):
    width = 30
    filled_length = int(width * percentage // 100)
    bar = '█' * filled_length + '░' * (width - filled_length)
    speed_part = f" {WHITE}{speed_text}{CLR}" if speed_text else ""
    sys.stdout.write(f"\r{CYAN}[*] {status_text} [{GREEN}{bar}{CYAN}] {percentage:>5.1f}%{speed_part}   ")
    sys.stdout.flush()

AUDIO_VIDEO_EXTENSIONS = (".mp3", ".wav", ".mp4", ".m4a", ".flac", ".webm", ".ogg", ".opus", ".mkv", ".weba")
INCOMPLETE_EXTENSIONS = (".part", ".ytdl", ".temp", ".ffmpeg", ".crdownload")

def get_media_files_snapshot(path):
    try:
        return {
            f for f in os.listdir(path)
            if f.lower().endswith(AUDIO_VIDEO_EXTENSIONS) and not f.lower().endswith(INCOMPLETE_EXTENSIONS)
        }
    except Exception:
        return set()

def execute_and_stream_output(cmd, platform):
    files_before = get_media_files_snapshot(SAVE_PATH)

    process = subprocess.Popen(
        cmd, 
        cwd=SAVE_PATH, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        universal_newlines=True, 
        encoding='utf-8', 
        errors='ignore',
        bufsize=1
    )
    
    current_track_num = 0
    has_errors = False
    error_logs = []
    
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
            
        line_str = line.strip()
        if line_str:
            error_logs.append(line_str)
            if len(error_logs) > 15:
                error_logs.pop(0)
            
            if "ERROR:" in line_str or "Failed" in line_str:
                has_errors = True
        
        if "[download]" in line_str and "Downloading item" in line_str:
            match_item = re.search(r'Downloading item (\d+) of (\d+)', line_str)
            if match_item:
                current_track_num = match_item.group(1)
                total_tracks = match_item.group(2)
                print(f"\n\n{WHITE}{BOLD}[Плейлист] Обработка трека {current_track_num} из {total_tracks}...{CLR}")
        
        if platform in ["YouTube", "SoundCloud"]:
            if "[download]" in line_str and "%" in line_str and "ETA" in line_str:
                match = re.search(r'(\d+\.\d+)%', line_str)
                if match:
                    pct = float(match.group(1))
                    speed_match = re.search(r'at\s+([\d.]+\S+/s)', line_str)
                    speed_text = speed_match.group(1) if speed_match else ""
                    render_progress_bar(pct, f"Загрузка #{current_track_num if current_track_num else 1} ", speed_text)
            elif "[ExtractAudio]" in line_str:
                print(f"\n{YELLOW}[*] Извлечение аудиопотока...{CLR}")
            elif "[ThumbnailsConvertor]" in line_str or "embed-thumbnail" in line_str.lower():
                print(f"{YELLOW}[*] Обработка обложки...{CLR}")
            elif "[Metadata]" in line_str or "embed-metadata" in line_str.lower():
                print(f"{YELLOW}[*] Сохранение метаданных...{CLR}")
                
        elif platform == "Spotify":
            if "Fetching" in line_str or "Searching" in line_str or "Found" in line_str:
                print(f"\n{YELLOW}[*] Поиск трека в базе данных...{CLR}")
            elif "Downloading" in line_str or "Downloaded" in line_str:
                match = re.search(r'(\d+)%', line_str)
                pct = float(match.group(1)) if match else 100.0
                render_progress_bar(pct, "Загрузка аудио")
            elif "Converting" in line_str or "Processing" in line_str:
                print(f"\n{YELLOW}[*] Применение тегов и финализация...{CLR}")

    process.wait()

    format_not_available = any("Requested format is not available" in l for l in error_logs)

    files_after = get_media_files_snapshot(SAVE_PATH)
    new_files = files_after - files_before
    already_had_file = any(
        ("already exists" in l.lower()) or ("skipping" in l.lower()) or ("already downloaded" in l.lower())
        for l in error_logs
    )
    disk_confirmed = bool(new_files) or already_had_file

    if not disk_confirmed:
        print(f"\n\n{RED}[-] Файлы не сохранены. Лог утилиты:{CLR}")
        for err_line in error_logs:
            if "ETA" not in err_line:
                print(f"{RED} > {err_line}{CLR}")
        return False, format_not_available, has_errors

    if new_files:
        print(f"\n{GREEN}[+] Успешно сохранено файлов: {len(new_files)}{CLR}")

    return True, format_not_available, has_errors

def build_ytdlp_command(ytdlp_bin, url, file_type, is_playlist, retry=False):
    ffmpeg_exe = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
    output_template = "%(playlist_index)02d - %(title)s.%(ext)s" if is_playlist else "%(title)s.%(ext)s"

    # Использование резервных клиентов при повторной попытке загрузки
    player_clients = "tv,web_safari" if retry else "ios,mweb,tv"

    base_args = [
        "--ffmpeg-location", FFMPEG_DIR,
        "-o", output_template,
        "--ignore-errors",
        "--no-warnings",
        "--embed-metadata",
        "--parse-metadata", "%(artist,uploader)s:artist",
        "--parse-metadata", "%(artist,uploader)s:album_artist",
        "--parse-metadata", "%(album)s:album",
        "--windows-filenames",
        "--extractor-args", f"youtube:player_client={player_clients}",
        "--remote-components", "ejs:github"
    ]
    base_args.extend(get_speed_args())

    if file_type == "mp3":
        fmt = "best" if retry else "bestaudio[abr>0]/bestaudio/best"
        cmd = [ytdlp_bin, "-f", fmt, "-x", "--audio-format", "mp3", "--audio-quality", "320K"]
        cmd.extend(base_args)
        cmd.extend(["--embed-thumbnail", "--convert-thumbnails", "jpg"])
    elif file_type == "wav":
        fmt = "best" if retry else "bestaudio[abr>0]/bestaudio/best"
        cmd = [ytdlp_bin, "-f", fmt, "-x", "--audio-format", "wav"]
        cmd.extend(base_args)
    else:
        fmt = "best" if retry else "bv*+ba/b/best"
        cmd = [ytdlp_bin, "-f", fmt, "--merge-output-format", "mp4"]
        cmd.extend(base_args)
        cmd.extend(["--embed-thumbnail"])
        cmd.extend(["--format-sort", "res,fps,hdr:12,vcodec:av01:vp9:h264,br,size"])

    if os.path.exists(COOKIES_PATH):
        cmd.extend(["--cookies", COOKIES_PATH])
    else:
        cmd.extend(["--cookies-from-browser", "chrome"])

    if not is_playlist:
        cmd.append("--no-playlist")

    cmd.append(url)
    return cmd

def execute_playlist_worker(cmd, worker_id, print_lock, shared_error_logs):
    try:
        process = subprocess.Popen(
            cmd,
            cwd=SAVE_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1
        )

        last_bucket = -1
        local_logs = []
        format_not_available = False
        has_error = False

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            line_str = line.strip()
            if not line_str:
                continue

            local_logs.append(line_str)
            if len(local_logs) > 15:
                local_logs.pop(0)

            if "Requested format is not available" in line_str:
                format_not_available = True
            
            if "ERROR:" in line_str or "Failed" in line_str:
                has_error = True

            if "[download]" in line_str and "%" in line_str and "ETA" in line_str:
                match = re.search(r'(\d+\.\d+)%', line_str)
                if match:
                    pct = float(match.group(1))
                    bucket = int(pct // 20) * 20
                    if bucket != last_bucket:
                        last_bucket = bucket
                        speed_match = re.search(r'at\s+([\d.]+\S+/s)', line_str)
                        speed_text = f" ({speed_match.group(1)})" if speed_match else ""
                        with print_lock:
                            print(f"{CYAN}[Поток {worker_id}]{CLR} {GREEN}{pct:>5.1f}%{CLR}{speed_text}")

        process.wait()
        with print_lock:
            shared_error_logs.extend(local_logs)
        return format_not_available, has_error

    except Exception as e:
        with print_lock:
            shared_error_logs.append(f"[-] Ошибка потока {worker_id}: {e}")
        return False, True

def process_playlist_parallel(ytdlp_bin, url, file_type, platform, retry=False):
    workers = PLAYLIST_WORKERS
    print(f"{CYAN}[*] Инициализация параллельной загрузки ({workers} потоков)...{CLR}\n")

    files_before = get_media_files_snapshot(SAVE_PATH)
    print_lock = threading.Lock()
    shared_error_logs = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = []
        for i in range(workers):
            cmd = build_ytdlp_command(ytdlp_bin, url, file_type, is_playlist=True, retry=retry)
            cmd.extend(["--playlist-items", f"{i + 1}::{workers}"])
            futures.append(pool.submit(execute_playlist_worker, cmd, i + 1, print_lock, shared_error_logs))
        results = [f.result() for f in futures]

    format_not_available = any(r[0] for r in results)
    has_errors = any(r[1] for r in results)

    files_after = get_media_files_snapshot(SAVE_PATH)
    new_files = files_after - files_before
    already_had_file = any(
        ("already exists" in l.lower()) or ("skipping" in l.lower()) or ("already downloaded" in l.lower())
        for l in shared_error_logs
    )
    disk_confirmed = bool(new_files) or already_had_file

    if new_files:
        print(f"\n{GREEN}[+] Успешно сохранено файлов: {len(new_files)}{CLR}")
    elif not disk_confirmed:
        print(f"\n{RED}[-] Ни один поток не сохранил файлы.{CLR}")
        for err_line in shared_error_logs[-15:]:
            if "ETA" not in err_line:
                print(f"{RED} > {err_line}{CLR}")

    return disk_confirmed, format_not_available, has_errors

def start_download_process(url, file_type, ytdlp_bin):
    url = clean_url(url)
    platform = get_platform(url)
    if not platform:
        print(f"\n{RED}[-] Ошибка: Платформа не поддерживается.{CLR}")
        return

    print(f"\n{GREEN}[+] Источник: {BOLD}{platform}{CLR} | {GREEN}Формат: {BOLD}{file_type.upper()}{CLR}")
    print(f"{CYAN}[*] Запуск обработки...{CLR}\n")
    
    is_playlist = is_playlist_url(url)
    ffmpeg_exe = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
    
    if platform == "Spotify":
        if file_type == "mp4":
            file_type = "mp3"
        cmd = [
            sys.executable, "-m", "spotdl", "download", url,
            "--format", file_type,
            "--bitrate", "320k",
            "--audio", "youtube-music", "youtube",
            "--threads", SPOTDL_THREADS,
            "--lyrics", "genius", "musixmatch",
            "--ffmpeg", ffmpeg_exe
        ]
        if os.path.exists(COOKIES_PATH):
            cmd.extend(["--cookie-file", COOKIES_PATH])

        try:
            success, _, has_errors = execute_and_stream_output(cmd, platform)
        except FileNotFoundError:
            print(f"\n{RED}[-] Модуль spotdl не найден. Дождитесь завершения фоновой установки.{CLR}")
            success = False
            has_errors = True

    else:
        if is_playlist and PLAYLIST_WORKERS > 1:
            success, format_not_available, has_errors = process_playlist_parallel(ytdlp_bin, url, file_type, platform, retry=False)
        else:
            cmd = build_ytdlp_command(ytdlp_bin, url, file_type, is_playlist, retry=False)
            try:
                success, format_not_available, has_errors = execute_and_stream_output(cmd, platform)
            except FileNotFoundError:
                print(f"\n{RED}[-] Утилита yt-dlp не найдена.{CLR}")
                success = False
                format_not_available = False
                has_errors = True

        if not success and format_not_available:
            print(f"\n{YELLOW}[~] Основные клиенты недоступны. Запуск резервного варианта...{CLR}\n")
            if is_playlist and PLAYLIST_WORKERS > 1:
                success, _, has_errors = process_playlist_parallel(ytdlp_bin, url, file_type, platform, retry=True)
            else:
                retry_cmd = build_ytdlp_command(ytdlp_bin, url, file_type, is_playlist, retry=True)
                try:
                    success, _, has_errors = execute_and_stream_output(retry_cmd, platform)
                except FileNotFoundError:
                    print(f"\n{RED}[-] Утилита yt-dlp не найдена.{CLR}")
                    success = False
                    has_errors = True

    print(f"\n{CYAN}──────────────────────────────────────────────────{CLR}")
    if success:
        if is_playlist and has_errors:
            print(f"{YELLOW}{BOLD}[~] Загрузка завершена (Частичный успех: некоторые файлы пропущены){CLR}")
        else:
            print(f"{GREEN}{BOLD}[+] Загрузка успешно завершена{CLR}")
        print(f"{WHITE}    Директория: {SAVE_PATH}{CLR}")
    else:
        print(f"{RED}[-] Загрузка прервана из-за ошибки.{CLR}")
    print(f"{CYAN}──────────────────────────────────────────────────{CLR}")

def read_single_keypress():
    if os.name == 'nt':
        while True:
            ch = msvcrt.getch()
            if ch == b'\x03': raise KeyboardInterrupt
            try:
                ch_str = ch.decode('utf-8')
                if ch_str in ['1', '2', '3']: return ch_str
            except Exception: pass
    else:
        return input("Выбор (1-3): ").strip()

def main():
    ensure_save_directory()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ytdlp_future = pool.submit(ensure_ytdlp)
        deno_future = pool.submit(ensure_deno)
        ytdlp_bin = ytdlp_future.result()
        deno_future.result()

    threading.Thread(target=ensure_aria2c_background, daemon=True).start()

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(update_tools, ytdlp_bin)
        pool.submit(ensure_spotdl_dependencies)
    
    while True:
        clear_screen()
        print(f"{CYAN}NovaDL  |  v1.0.0{CLR}")
        print(f"{CYAN}──────────────────────────────────────────────────{CLR}")
        print(f"{WHITE}• Сохранение:  {YELLOW}{SAVE_PATH}{CLR}")
        print(f"{WHITE}• Файл куки:   {GREEN}{'Активен' if os.path.exists(COOKIES_PATH) else 'Не найден (используется браузер)'}{CLR}")
        print(f"{CYAN}──────────────────────────────────────────────────{CLR}")
        
        url = input(f"{WHITE}URL (0 - настройки, Enter - выход):{CLR} ").strip()
        if not url: break
        
        if url == '0':
            prompt_change_save_directory()
            input(f"\n{WHITE}Нажмите Enter для продолжения...{CLR}")
            continue
            
        print(f"\n{WHITE}Выберите формат:{CLR}")
        print(f" {GREEN}1.{CLR} MP3  {WHITE}(Аудио 320kbps + обложка + теги){CLR}")
        print(f" {GREEN}2.{CLR} WAV  {WHITE}(Lossless аудио без сжатия){CLR}")
        print(f" {GREEN}3.{CLR} MP4  {WHITE}(Видео в максимальном качестве){CLR}")
        print(f"{CYAN}──────────────────────────────────────────────────{CLR}")
        
        choice = read_single_keypress()
        
        file_type = "mp3"
        if choice == '2': file_type = "wav"
        elif choice == '3': file_type = "mp4"
        
        try:
            start_download_process(url, file_type, ytdlp_bin)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"\n{RED}[-] Системная ошибка: {e}{CLR}")
            
        input(f"\n{WHITE}Нажмите Enter для продолжения...{CLR}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)