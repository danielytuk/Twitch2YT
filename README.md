
# Twitch2YT

## Summary

**Twitch2YT** is a Python-based tool that automatically relays a Twitch stream to a YouTube channel in real-time. It continuously monitors the Twitch stream, fetches the highest quality available, and uses FFmpeg to broadcast it to YouTube. The tool supports CPU/GPU-based video encoding and handles automatic restarts when streams go offline or FFmpeg processes terminate.

$\textcolor{red}{Note:\ VirusTotal\ may\ detect\ this\ project\ as\ Malicious.\ It's\ a\ false\ positive.\}$

---

## Features

* Automatically fetches Twitch stream status and available stream qualities.
* Relays live Twitch streams to YouTube using **FFmpeg**.
* Supports GPU encoding if available (`h264_nvenc`, `h264_amf`, `h264_qsv`).
* Automatically detects system resources and adjusts FFmpeg performance for low CPU/RAM setups.
* Handles stream interruptions gracefully and restarts FFmpeg as needed.
* Supports upgrading to higher quality streams if they become available mid-stream.
* Simple configuration via a JSON file or interactive setup.

---

## Installation

### Download

You can purchase the bundled executable for £5 GBP: [buymeacoffee/danielytuk](https://buymeacoffee.com/danielytuk/e/464645)

### Prerequisites

* Python 3.10+
* FFmpeg installed and accessible in the system path (the script can detect FFmpeg automatically using `imageio-ffmpeg`)
* Required Python packages:

  ```bash
  pip install streamlink imageio-ffmpeg psutil
  ```

### Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/danielytuk/Twitch2YT.git
   cd Twitch2YT
   ```
2. Run the script to create a configuration file:

   ```bash
   python Twitch2YT.py
   ```
3. Enter your **Twitch username or URL** and **YouTube stream key** when prompted. This will generate a `config.json` file.

---

## How It Works

### Twitch Stream Fetching

The script uses the [Streamlink](https://streamlink.github.io/) library to:

1. Fetch all available Twitch stream qualities (excluding audio-only streams).
2. Select the best quality automatically or upgrade to a higher quality if it becomes available while streaming.

Functions involved:

* `get_available_streams()`: Retrieves all available Twitch streams.
* `pick_best_stream(streams)`: Chooses the best stream from available options.

---

### FFmpeg Relay

The script leverages **FFmpeg** to broadcast the Twitch stream to YouTube via RTMP.

1. **FFmpeg Setup**

   * Detects the FFmpeg executable using `imageio-ffmpeg`.
   * Checks for GPU encoders (`h264_nvenc`, `h264_amf`, `h264_qsv`) to optimize performance.
   * Adjusts CPU thread usage and buffering if the system has low resources.

2. **Relay Execution**

   * Streams the selected Twitch video to YouTube in real-time using FFmpeg.
   * Automatically restarts FFmpeg if the process ends unexpectedly or reaches the maximum runtime (`10.5 hours`).
   * Upgrades the stream to higher quality if detected during an ongoing relay.

3. **Process Management**

   * Active FFmpeg processes are tracked to prevent duplicates.
   * Graceful termination and restart of processes to maintain continuous relay.

Key functions:

* `start_ffmpeg(stream, quality)`: Launches FFmpeg for relaying.
* `Relay` class: Handles monitoring Twitch, restarting FFmpeg, and upgrading stream quality.

---

### System Resource Adaptation

* **CPU detection:** Adjusts FFmpeg thread count for low CPU machines.
* **RAM detection:** Modifies FFmpeg buffer sizes for low-memory systems.
* **GPU encoding:** Uses hardware acceleration if available to reduce CPU load.

---

### Logging

The script uses Python’s built-in logging module:

* Logs Twitch stream status changes (`online`, `offline`).
* Logs FFmpeg starts, upgrades, and unexpected terminations.
* Provides concise and readable logs suitable for long-running processes.

---

## Configuration

The configuration is stored in `config.json`:

```json
{
  "username": "twitch_username",
  "youtube_key": "your_youtube_stream_key"
}
```

* `username`: Twitch username or URL to relay.
* `youtube_key`: YouTube stream key (found in your YouTube Studio live dashboard).

---

## Usage

Simply run:

```bash
python Twitch2YT.py
```

* The script will wait until the Twitch stream goes live.
* Once live, it will start relaying to YouTube automatically.
* Monitor logs for status updates.

---

## Notes

* Make sure your Twitch account is public or that the stream is accessible for relaying.
* The script does not handle Twitch or YouTube authentication beyond public streams and a stream key.

---

## Contributing

Contributions are welcome! Feel free to submit bug reports or feature requests via GitHub Issues.

---

## License

MIT License – see [LICENSE](LICENSE) for details.
