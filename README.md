# MoM Toolbox

A free Windows desktop tool that turns meetings into **Minutes of Meeting (MoM)**:

1. **Record** the meeting audio playing on your computer (Teams, Zoom, Meet, etc.)
2. **Transcribe** audio or video files into a timestamped transcript (offline, using faster-whisper)
3. **Generate MoM** from the transcript with a local LLM (Ollama) or a cloud LLM (Claude or Gemini)

Everything runs in your browser from a single app with a sidebar to switch between the recorder and the transcript / MoM tools.

## Download

Go to the **[Releases](../../releases/latest)** page and download one of these (Windows 10/11, 64-bit):

| File | What it is |
|---|---|
| `MoM_Toolbox_Setup_vX.Y.Z.exe` | Installer. Adds desktop and Start-menu shortcuts. No admin rights needed. |
| `MoM_Toolbox_Portable_vX.Y.Z.zip` | No install. Unzip anywhere and double-click `MoM_Toolbox.exe`. |

The installer is not code-signed, so Windows may show **"Windows protected your PC"**. Click **More info → Run anyway**.

### Verify your download

Each release includes `SHA256SUMS.txt`. In PowerShell, run:

```powershell
Get-FileHash .\MoM_Toolbox_Setup_vX.Y.Z.exe -Algorithm SHA256
```

The hash must match the line for that file in `SHA256SUMS.txt`.

## Using it

- Start **MoM Toolbox**. A console window opens and the app opens in your browser. Keep the console window open while you use the app; close it to quit.
- **System Audio Recorder** captures whatever plays through the selected speaker/headphone. Recordings are saved to `Documents\MoM Toolbox\Recordings`.
- **Transcript & MoM → Audio/Video to Transcript** accepts uploads (up to 200 MB) or a local file path (any size). The first transcription downloads the Whisper "base" model (about 145 MB), so it needs internet once.
- **Transcript & MoM → Minutes of Meeting** works with:
  - **Ollama (local, free):** install [Ollama](https://ollama.com/download), then run `ollama pull mistral`.
  - **Claude API:** needs an API key from [console.anthropic.com](https://console.anthropic.com).
  - **Google Gemini:** needs an API key from [aistudio.google.com](https://aistudio.google.com).

API keys are typed into the app each time and are not saved.

## Build it yourself

Requires Windows and Python 3.12.

```bat
git clone https://github.com/rajaguruirusan/mom-toolbox.git
cd mom-toolbox
BUILD.bat
```

`BUILD.bat` creates a build environment, installs the exact package versions in `requirements-lock.txt` (every download is hash-checked), downloads a pinned ffmpeg build and checks its SHA-256, builds the app with PyInstaller and packages it with Inno Setup. The results are in the `release` folder.

To run from source without building:

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install --require-hashes -r requirements-lock.txt
.venv\Scripts\python launcher.py
```

Put `ffmpeg.exe` and `ffprobe.exe` in an `ffmpeg` folder next to `launcher.py` (BUILD.bat does this for you).

## Releasing a new version

Releases are built automatically by GitHub Actions (`.github/workflows/release.yml`):

- **Actions → Build and Release → Run workflow**, enter a version such as `1.1.0`, or
- push a tag such as `v1.1.0`.

The workflow builds the installer and the portable zip on Windows and attaches them, with `SHA256SUMS.txt`, to a new release. The build uses hash-locked Python packages, checksum-verified ffmpeg and Inno Setup downloads, and GitHub Actions pinned to exact commits.

To update dependencies, edit `requirements.txt`, then regenerate the lockfile:

```bash
uv pip compile requirements.txt build-tools.in --python-platform x86_64-pc-windows-msvc --python-version 3.12 --generate-hashes --no-header --no-annotate -o requirements-lock.txt
```

## Project layout

| Path | Purpose |
|---|---|
| `app/Home.py` | Streamlit entry point with sidebar navigation |
| `app/recorder_page.py` | System audio (WASAPI loopback) recorder |
| `app/mom_page.py` | Audio/video → transcript and transcript → MoM |
| `app/toolbox_paths.py` | Locates the bundled ffmpeg and the recordings folder |
| `launcher.py` | Starts the Streamlit server and opens the browser |
| `MoM_Toolbox.spec` | PyInstaller build recipe |
| `installer.iss` | Inno Setup installer script |

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).

The packaged app includes ffmpeg 9.0.2 "essentials" builds from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (downloaded from the [GyanD/codexffmpeg](https://github.com/GyanD/codexffmpeg) GitHub releases), licensed under GPL v3.
