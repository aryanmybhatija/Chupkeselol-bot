import subprocess
import os
import re

def get_video_duration(file_path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180
        )
        duration_str = result.stdout.strip()

        # ✅ Real float check
        try:
            duration = float(duration_str)
            return int(duration)
        except ValueError:
            print("⚠️ Invalid duration format:", duration_str)
            return 0

    except subprocess.TimeoutExpired:
        print("⚠️ ffprobe timed out")
        return 0
    except Exception as e:
        print(f"⚠️ Duration error: {e}")
        return 0

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)
