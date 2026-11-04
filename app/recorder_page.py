import streamlit as st
import os
import subprocess
import threading
import time
import wave
import struct
from datetime import datetime

st.title("🎙️ System Audio Recorder")
st.caption("Records system audio (loopback) — captures whatever plays through your speakers/headphones.")

# ---------- Import pyaudiowpatch ----------
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    st.error("❌ `PyAudioWPatch` not installed. Run:\n\n`pip install PyAudioWPatch`")
    st.stop()

# ---------- Shared state (survives Streamlit reruns via Python import cache) ----------
import _recorder_state as RS
import toolbox_paths

# ---------- Config ----------
OUTPUT_DIR = toolbox_paths.recordings_dir()

# ---------- Session State ----------
for key, default in [("recording", False), ("recorded_file", None), ("start_time", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------- Detect WASAPI loopback devices (cached) ----------
@st.cache_data(ttl=60)
def get_loopback_devices():
    """Detect WASAPI loopback devices. Cached so PyAudio init only runs once."""
    pa = pyaudio.PyAudio()
    devices = []
    try:
        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            if dev["hostApi"] == wasapi_info["index"] and dev.get("isLoopbackDevice", False):
                devices.append({
                    "index": dev["index"],
                    "name": dev["name"],
                    "defaultSampleRate": dev["defaultSampleRate"],
                    "maxInputChannels": dev["maxInputChannels"],
                })
    except Exception as e:
        pa.terminate()
        return None, str(e)
    pa.terminate()
    return devices, None

st.subheader("🔊 Audio Output Device")

loopback_devices, error = get_loopback_devices()

if error:
    st.error(f"Could not detect WASAPI loopback devices: {error}")
    st.stop()

if not loopback_devices:
    st.warning("No WASAPI loopback devices found. Make sure you have an active audio output device.")
    st.stop()

device_names = [d["name"] for d in loopback_devices]
selected_name = st.selectbox(
    "Select the speaker/headphone to capture from:",
    device_names,
    index=0,
    help="This captures audio playing through this output device (loopback)."
)
selected_device = loopback_devices[device_names.index(selected_name)]

# ---------- Recording settings ----------
st.subheader("⚙️ Settings")
col1, col2 = st.columns(2)
with col1:
    max_duration = st.number_input("Max duration (minutes):", min_value=1, max_value=180, value=60, step=5)
with col2:
    output_format = st.selectbox("Output format:", ["WAV", "MP3"], index=0)

# ---------- Recording logic ----------
def record_audio(device_info, duration_sec):
    """Record WASAPI loopback audio in a background thread.

    Uses the WASAPI loopback device in its native format (float32),
    then converts to int16 for WAV output.
    Communicates via _recorder_state module (RS).
    """
    sample_rate = int(device_info["defaultSampleRate"])
    channels = int(device_info["maxInputChannels"])
    device_index = device_info["index"]
    chunk_frames = 512

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = os.path.join(OUTPUT_DIR, f"system_audio_{timestamp}.wav")

    pa = pyaudio.PyAudio()
    total_bytes_written = 0
    try:
        stream = pa.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=chunk_frames,
        )

        wf = wave.open(wav_path, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)

        frames_recorded = 0
        max_frames = duration_sec * sample_rate

        while frames_recorded < max_frames and not RS.stop_event.is_set():
            data = stream.read(chunk_frames, exception_on_overflow=False)

            # Convert float32 → int16
            num_samples = len(data) // 4
            float_samples = struct.unpack(f'{num_samples}f', data)
            int16_samples = []
            for s in float_samples:
                s = max(-1.0, min(1.0, s))
                int16_samples.append(int(s * 32767))
            int16_data = struct.pack(f'{num_samples}h', *int16_samples)
            wf.writeframes(int16_data)
            total_bytes_written += len(int16_data)
            frames_recorded += chunk_frames

        wf.close()
        stream.stop_stream()
        stream.close()

        with RS.result_lock:
            RS.result_file[0] = wav_path if total_bytes_written > 0 else None

    except Exception as e:
        with RS.result_lock:
            RS.result_file[0] = None
        try:
            with open(os.path.join(OUTPUT_DIR, "recorder_debug.log"), "a") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Recording error: {e}\n")
        except:
            pass
    finally:
        pa.terminate()

# ---------- Controls ----------
st.subheader("🎬 Controls")

col_start, col_stop = st.columns(2)

with col_start:
    if st.button("🔴 Start Recording", type="primary", disabled=st.session_state.recording, use_container_width=True):
        st.session_state.recording = True
        st.session_state.recorded_file = None
        st.session_state.start_time = time.time()

        RS.stop_event.clear()
        with RS.result_lock:
            RS.result_file[0] = None

        thread = threading.Thread(
            target=record_audio,
            args=(selected_device, max_duration * 60),
            daemon=True
        )
        thread.start()
        st.rerun()

with col_stop:
    if st.button("⬛ Stop Recording", disabled=not st.session_state.recording, use_container_width=True):
        RS.stop_event.set()
        st.session_state.recording = False
        time.sleep(1.5)

        with RS.result_lock:
            st.session_state.recorded_file = RS.result_file[0]

        st.rerun()

# ---------- Status ----------
if st.session_state.recording:
    st.warning("🔴 Recording in progress... Click **Stop Recording** when done.")

# ---------- Save & Download ----------
if not st.session_state.recording and st.session_state.recorded_file is not None:
    wav_path = st.session_state.recorded_file

    if os.path.exists(wav_path) and os.path.getsize(wav_path) > 44:
        file_size = os.path.getsize(wav_path)
        with wave.open(wav_path, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_secs = frames / rate
        mins, secs = divmod(int(duration_secs), 60)
        st.success(f"✅ Recording complete! Duration: **{mins}m {secs}s** | Size: {file_size / (1024*1024):.1f} MB")

        if output_format == "MP3":
            mp3_path = wav_path.replace(".wav", ".mp3")
            subprocess.run([toolbox_paths.ffmpeg_exe(), "-y", "-i", wav_path, "-q:a", "2", mp3_path],
                           capture_output=True)
            if os.path.exists(mp3_path):
                file_path = mp3_path
                file_name = os.path.basename(mp3_path)
                mime_type = "audio/mpeg"
                os.remove(wav_path)
            else:
                file_path = wav_path
                file_name = os.path.basename(wav_path)
                mime_type = "audio/wav"
                st.warning("MP3 conversion failed (ffmpeg not found?). Saving as WAV instead.")
        else:
            file_path = wav_path
            file_name = os.path.basename(wav_path)
            mime_type = "audio/wav"

        st.audio(file_path)

        with open(file_path, "rb") as f:
            st.download_button(
                label=f"📥 Download {file_name}",
                data=f.read(),
                file_name=file_name,
                mime=mime_type,
                use_container_width=True
            )

        st.info(f"💾 Saved to: `{file_path}`\n\nYou can now use this file in **Transcript & MoM** (Local file path mode) for transcription.")
    else:
        st.error("❌ Recording produced an empty file. Make sure audio is playing through the selected output device during recording.")

# ---------- Footer ----------
st.divider()
st.caption("Tip: This recorder captures system audio via WASAPI loopback. Make sure your meeting audio is playing through the selected output device.")

# (Timer is pure JS — no Python sleep or rerun needed)
