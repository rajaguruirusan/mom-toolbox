import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

datas = [("app", "app")]
binaries = []
hiddenimports = [
    "recorder_page",
    "mom_page",
    "toolbox_paths",
    "_recorder_state",
    "_portaudiowpatch",
    "wave",
    "audioop",
    "struct",
    "tempfile",
    "json",
    "subprocess",
    "ctypes.wintypes",
]

for pkg in ["streamlit", "faster_whisper", "ctranslate2", "av", "tokenizers", "pyaudiowpatch", "moviepy", "proglog", "hf_xet"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

for pkg in [
    "uvicorn", "starlette", "websockets", "httptools", "anyio", "h11",
    "httpx", "httpcore", "httpx2", "httpcore2",
    "huggingface_hub", "anthropic", "google.genai", "ollama", "pydub", "imageio",
]:
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

for dist in [
    "streamlit", "faster-whisper", "ctranslate2", "tokenizers", "huggingface-hub", "tqdm",
    "requests", "packaging", "filelock", "numpy", "regex", "imageio", "moviepy", "hf-xet",
    "anthropic", "google-genai", "ollama", "httpx", "pydantic", "uvicorn", "starlette",
]:
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

excludes = [
    "torch", "torchvision", "torchaudio", "torchgen", "functorch", "whisper",
    "numba", "llvmlite", "sympy", "tiktoken", "triton", "tkinter", "matplotlib",
    "IPython", "pytest",
]

a = Analysis(
    ["launcher.py"],
    pathex=[os.path.abspath("app")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

a.datas = [d for d in a.datas if not ("imageio_ffmpeg" in d[0] and "binaries" in d[0])]
a.binaries = [b for b in a.binaries if not ("imageio_ffmpeg" in b[0] and "binaries" in b[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MoM_Toolbox",
    icon="mom.ico",
    console=True,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="MoM_Toolbox",
)
