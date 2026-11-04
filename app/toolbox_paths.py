import os
import sys


def _is_frozen():
    return getattr(sys, "frozen", False)


def _exe_name(name):
    return name + ".exe" if os.name == "nt" else name


def ffmpeg_dir():
    candidates = []
    if _is_frozen():
        candidates.append(os.path.join(os.path.dirname(sys.executable), "ffmpeg"))
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(os.path.dirname(app_dir), "ffmpeg"))
    for c in candidates:
        if os.path.isfile(os.path.join(c, _exe_name("ffmpeg"))):
            return c
    return None


def ffmpeg_exe():
    d = ffmpeg_dir()
    return os.path.join(d, _exe_name("ffmpeg")) if d else "ffmpeg"


def ffprobe_exe():
    d = ffmpeg_dir()
    return os.path.join(d, _exe_name("ffprobe")) if d else "ffprobe"


def prepare_ffmpeg():
    d = ffmpeg_dir()
    if not d:
        return
    path = os.environ.get("PATH", "")
    if d not in path.split(os.pathsep):
        os.environ["PATH"] = d + os.pathsep + path
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.join(d, _exe_name("ffmpeg"))


def _documents_dir():
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return buf.value
        except Exception:
            pass
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return docs if os.path.isdir(docs) else os.path.expanduser("~")


def recordings_dir():
    d = os.path.join(_documents_dir(), "MoM Toolbox", "Recordings")
    os.makedirs(d, exist_ok=True)
    return d
