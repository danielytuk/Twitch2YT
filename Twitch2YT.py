import os, json, time, logging, threading, subprocess
import streamlink
from urllib.parse import urlparse
import imageio_ffmpeg as iio_ffmpeg

# --- Config ---
CONFIG_FILE = "config.json"
FFMPEG_MAX_RUNTIME = 10.5*60*60
cpu_cores = os.cpu_count() or 1
try:
    import psutil
    total_ram_gb = psutil.virtual_memory().total / (1024**3)
except:
    total_ram_gb = 8
low_cpu = cpu_cores <= 2
low_ram = total_ram_gb <= 4

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s | %(message)s", datefmt="%H:%M:%S", level=logging.INFO
)
logger = logging.getLogger("twitch2yt")

# --- FFmpeg Helpers ---
def get_ffmpeg_path():
    path = iio_ffmpeg.get_ffmpeg_exe()
    if not os.path.isfile(path):
        raise RuntimeError(f"FFmpeg missing at {path}")
    if not os.access(path, os.X_OK):
        if os.name == "nt" and not path.endswith(".exe") and os.path.isfile(path+".exe"):
            path += ".exe"
        else:
            raise RuntimeError(f"FFmpeg not executable at {path}")
    return path

def detect_gpu_encoder():
    try:
        out = subprocess.run([get_ffmpeg_path(), "-encoders"], capture_output=True, text=True, check=True).stdout.lower()
        if "h264_nvenc" in out: return "h264_nvenc"
        elif "h264_amf" in out or "h264_qsv" in out:
            return "h264_amf" if "h264_amf" in out else "h264_qsv"
    except:
        return None

gpu_encoder = detect_gpu_encoder()

# --- Config Loader ---
def load_config():
    while True:
        if not os.path.exists(CONFIG_FILE):
            cfg = {}
            twitch = input("Twitch username or URL: ").strip()
            if twitch.startswith("http"):
                try:
                    p = urlparse(twitch)
                    if p.netloc not in ("twitch.tv", "www.twitch.tv"): raise ValueError()
                    u = p.path.strip("/")
                    cfg["username"] = u or None
                except:
                    print("Invalid Twitch URL")
                    continue
            else:
                cfg["username"] = twitch if twitch else None
            cfg["youtube_key"] = input("YouTube stream key: ").strip()
            with open(CONFIG_FILE, "w") as f: json.dump(cfg, f)
            print(f"Config saved to {CONFIG_FILE}")
        else:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
        return cfg

config = load_config()
TWITCH_USER = config["username"]
YOUTUBE_KEY = config["youtube_key"]
YOUTUBE_RTMP = f"rtmps://a.rtmps.youtube.com/live2/{YOUTUBE_KEY}"

# --- Stream Helpers ---
def get_available_streams():
    try:
        return {n: s for n, s in streamlink.streams(f"https://www.twitch.tv/{TWITCH_USER}").items() if "audio" not in n.lower()}
    except:
        return {}

def pick_best_stream(streams):
    if "best" in streams: return "best", streams["best"]
    qs = [q for q in streams if any(c.isdigit() for c in q)]
    if qs:
        best_q = sorted(qs, reverse=True)[0]
        return best_q, streams[best_q]
    return next(iter(streams.items()))

# --- Track active processes ---
active_processes = {}
process_lock = threading.Lock()

# --- FFmpeg Relay ---
def start_ffmpeg(stream, quality, retries=3):
    global active_processes
    try:
        url = stream.to_url()
    except Exception as e:
        logger.error(f"Cannot get stream URL: {e}")
        return None

    ffmpeg_path = get_ffmpeg_path()

    for attempt in range(1, retries+1):
        cmd = [ffmpeg_path, "-nostats", "-loglevel", "warning", "-re", "-i", url,
               "-c:a", "aac", "-ar", "44100", "-b:a", "128k", "-ac", "2",
               "-f", "flv", YOUTUBE_RTMP]

        encoder_used = "copy"
        if gpu_encoder:
            cmd.insert(7, "-c:v"); cmd.insert(8, gpu_encoder)
            encoder_used = gpu_encoder

        adjustments = ""
        if low_cpu or low_ram:
            cmd += ["-threads", str(max(1, cpu_cores)), "-bufsize", "2M", "-fflags", "+genpts"]
            adjustments = f" | CPU={cpu_cores} RAM={total_ram_gb:.1f}GB"

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            with process_lock:
                old_proc = active_processes.get(TWITCH_USER)
                if old_proc and old_proc != proc:
                    old_proc.terminate(); old_proc.wait(timeout=10)
                active_processes[TWITCH_USER] = proc

            # Ultra-clean log: single line per FFmpeg start
            logger.info(f"FFmpeg PID {proc.pid} started | Quality: {quality} | Encoder: {encoder_used}{adjustments}")
            return proc
        except Exception as e:
            logger.warning(f"FFmpeg attempt {attempt} failed: {e}")
            time.sleep(3)
    return None

# --- Relay ---
class Relay:
    def __init__(self):
        self.current_ffmpeg = None
        self.current_quality = None
        self.start_time = None
        self.lock = threading.Lock()
        self.stream_obj = None
        self.last_stream_status = None
        self.last_upgrade_logged = False

    def wait_for_stream(self):
        while True:
            streams = get_available_streams()
            if streams:
                quality, stream = pick_best_stream(streams)
                if stream:
                    if self.last_stream_status != "online":
                        logger.info(f"Twitch stream online | Quality: {quality}")
                        self.last_stream_status = "online"
                    return quality, stream
            if self.last_stream_status != "offline":
                logger.info("Waiting for Twitch stream...")
                self.last_stream_status = "offline"
            time.sleep(15)

    def start_relay(self):
        while True:
            quality, stream = self.wait_for_stream()
            with self.lock:
                self.start_new_ffmpeg(stream, quality)
            while True:
                time.sleep(30)
                with self.lock:
                    if not self.current_ffmpeg or self.current_ffmpeg.poll() is not None:
                        logger.info("FFmpeg ended unexpectedly, restarting...")
                        break
                    elapsed = time.time() - self.start_time
                    if elapsed > FFMPEG_MAX_RUNTIME:
                        logger.info("Max runtime reached, restarting FFmpeg...")
                        self.start_new_ffmpeg(stream, quality)
                        break
                    streams = get_available_streams()
                    if "best" in streams and self.current_quality != "best":
                        if not self.last_upgrade_logged:
                            logger.info("Higher quality available, upgrading...")
                            self.last_upgrade_logged = True
                        self.start_new_ffmpeg(streams["best"], "best")
                        break
                    else:
                        self.last_upgrade_logged = False
                    if not streams and self.last_stream_status != "offline":
                        logger.info("Stream offline, waiting...")
                        self.last_stream_status = "offline"
                        break

    def start_new_ffmpeg(self, stream, quality):
        new_ffmpeg = start_ffmpeg(stream, quality)
        if not new_ffmpeg:
            logger.error(f"Failed to start FFmpeg for {quality}, retrying in 10s")
            time.sleep(10)
            return
        if self.current_ffmpeg and self.current_ffmpeg != new_ffmpeg:
            logger.info(f"Stopping previous FFmpeg PID {self.current_ffmpeg.pid}")
            self.current_ffmpeg.terminate()
            try: self.current_ffmpeg.wait(timeout=10)
            except: self.current_ffmpeg.kill()
        self.current_ffmpeg = new_ffmpeg
        self.current_quality = quality
        self.start_time = time.time()
        self.stream_obj = stream

# --- Main ---
if __name__ == "__main__":
    relay = Relay()
    try:
        logger.info("Support: www.dytuk.media/pay")
        relay.start_relay()
    except KeyboardInterrupt:
        logger.info("Exiting...")
    if relay.current_ffmpeg:
        relay.current_ffmpeg.terminate()
        relay.current_ffmpeg.wait()
