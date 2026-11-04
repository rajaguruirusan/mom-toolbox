import os
import subprocess
import json

# ---------- FFmpeg Config ----------
import toolbox_paths
toolbox_paths.prepare_ffmpeg()

import streamlit as st
import tempfile
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from faster_whisper import WhisperModel
from datetime import timedelta
import ollama
import math
try:
    import anthropic
except ImportError:
    anthropic = None
try:
    from google import genai
except ImportError:
    genai = None

AudioSegment.converter = toolbox_paths.ffmpeg_exe()
AudioSegment.ffprobe   = toolbox_paths.ffprobe_exe()

# ---------- Config ----------
CHUNK_DURATION_MIN = 5   # minutes per transcription chunk
GAP_THRESHOLD = 1.5      # seconds of silence to start new paragraph

# ---------- Helper Functions ----------

def format_timestamp(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))

def get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [toolbox_paths.ffprobe_exe(), "-v", "quiet", "-print_format", "json", "-show_format", file_path],
            capture_output=True, text=True
        )
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except Exception:
        return 0.0

def extract_audio_ffmpeg(input_path: str, output_path: str):
    """Extract audio from video using ffmpeg directly — fast, no RAM issues for large files."""
    cmd = [
        toolbox_paths.ffmpeg_exe(), "-y", "-i", input_path,
        "-vn",                    # no video
        "-acodec", "pcm_s16le",   # wav format
        "-ar", "16000",           # 16kHz for Whisper
        "-ac", "1",               # mono
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
    return output_path

def convert_video_to_audio(video_file, out_format="wav"):
    """Convert uploaded video file to audio."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        temp_video.write(video_file.read())
        temp_video_path = temp_video.name

    video = VideoFileClip(temp_video_path)
    audio_temp_path = temp_video_path + f".{out_format}"
    if out_format == "wav":
        video.audio.write_audiofile(audio_temp_path, codec="pcm_s16le", fps=16000)
    else:
        video.audio.write_audiofile(audio_temp_path)
    video.close()
    try:
        os.remove(temp_video_path)
    except Exception:
        pass
    return audio_temp_path

def merge_audio_files(audio_paths, out_format="wav"):
    """Merge multiple audio files into one."""
    merged = AudioSegment.empty()
    for p in audio_paths:
        audio = AudioSegment.from_file(p)
        merged += audio
    merged_path = os.path.join(tempfile.gettempdir(), f"merged_output.{out_format}")
    if out_format == "wav":
        merged.export(merged_path, format=out_format, parameters=["-ar", "16000", "-ac", "1"])
    else:
        merged.export(merged_path, format=out_format)
    return merged_path

def split_audio_to_chunks(file_path: str, chunk_min: int) -> list:
    """Split audio into chunks. Returns list of (chunk_path, offset_seconds)."""
    audio = AudioSegment.from_file(file_path)
    chunk_ms = chunk_min * 60 * 1000
    chunks = []
    for i in range(0, len(audio), chunk_ms):
        chunk = audio[i:i + chunk_ms]
        chunk_path = os.path.join(tempfile.gettempdir(), f"r2m_chunk_{i // chunk_ms}.wav")
        chunk.export(chunk_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])
        chunks.append((chunk_path, i / 1000.0))
    return chunks

def group_into_paragraphs(segments, offset: float) -> list:
    """Group segments into paragraphs based on silence gaps."""
    paragraphs = []
    if not segments:
        return paragraphs

    curr_para = []
    para_start = segments[0]["start"] + offset
    last_end = segments[0]["end"] + offset
    curr_para.append(segments[0]["text"].strip())

    for seg in segments[1:]:
        seg_start = seg["start"] + offset
        seg_end = seg["end"] + offset
        gap = seg["start"] + offset - last_end
        if gap > GAP_THRESHOLD:
            para_text = " ".join(curr_para)
            paragraphs.append(
                f"[{format_timestamp(para_start)} - {format_timestamp(last_end)}] {para_text}"
            )
            curr_para = [seg["text"].strip()]
            para_start = seg_start
        else:
            curr_para.append(seg["text"].strip())
        last_end = seg_end

    if curr_para:
        para_text = " ".join(curr_para)
        paragraphs.append(
            f"[{format_timestamp(para_start)} - {format_timestamp(last_end)}] {para_text}"
        )
    return paragraphs

def transcribe_audio_chunked(audio_path, progress_bar, status_text):
    """Transcribe audio using faster-whisper with chunked processing and progress bar."""
    status_text.text("Splitting audio into chunks...")
    chunks = split_audio_to_chunks(audio_path, CHUNK_DURATION_MIN)
    total_chunks = len(chunks)

    status_text.text("Loading faster-whisper model...")
    progress_bar.progress(0)
    model = WhisperModel("base", device="cpu", compute_type="int8")

    all_paragraphs = []
    for idx, (chunk_path, offset) in enumerate(chunks):
        pct = int((idx / total_chunks) * 100)
        status_text.text(f"Transcribing chunk {idx + 1} of {total_chunks}... ({pct}%)")
        progress_bar.progress(pct)

        segments_iter, info = model.transcribe(chunk_path, language="en", task="transcribe")
        segments = [{"start": s.start, "end": s.end, "text": s.text} for s in segments_iter]
        chunk_paragraphs = group_into_paragraphs(segments, offset)
        all_paragraphs.extend(chunk_paragraphs)

        try:
            os.remove(chunk_path)
        except Exception:
            pass

    progress_bar.progress(100, text="✅ Transcription complete!")
    status_text.empty()
    return all_paragraphs

def split_text_into_chunks(text, chunk_size_words):
    words = text.split()
    num_chunks = math.ceil(len(words) / chunk_size_words)
    return [
        " ".join(words[i * chunk_size_words:(i + 1) * chunk_size_words])
        for i in range(num_chunks)
    ]

def check_ollama_available():
    """Check if Ollama is running and accessible."""
    try:
        ollama.list()
        return True
    except Exception:
        return False

# =============== UI ===============

st.title("📑 Meeting Audio/Transcript Toolbox")
st.caption("Powered by faster-whisper (int8) · Chunked processing with progress bar")

tab1, tab2 = st.tabs([
    "1️⃣ Audio/Video to Transcript",
    "2️⃣ Minutes of Meeting (from Transcript)"
])

# =================== TAB 1 ===================
with tab1:
    st.header("🎬 Convert, Merge & Transcribe")

    # --- Input mode toggle ---
    input_mode = st.radio(
        "How would you like to provide the file?",
        ("Upload file (< 200 MB)", "Local file path (any size)"),
        horizontal=True
    )

    audio_to_transcribe = None  # will hold the final audio path to transcribe
    cleanup_paths = []          # temp files to clean up

    if input_mode == "Upload file (< 200 MB)":
        st.write("Upload up to 5 audio/video files. Videos are converted to audio, all files are merged, then transcribed.")
        SUPPORTED_TYPES = ["mp4", "webm", "mp3", "m4a", "wav", "ogg", "flac"]
        file1 = st.file_uploader("File 1", type=SUPPORTED_TYPES, key="f1")
        file2 = st.file_uploader("File 2 (optional)", type=SUPPORTED_TYPES, key="f2")
        file3 = st.file_uploader("File 3 (optional)", type=SUPPORTED_TYPES, key="f3")
        file4 = st.file_uploader("File 4 (optional)", type=SUPPORTED_TYPES, key="f4")
        file5 = st.file_uploader("File 5 (optional)", type=SUPPORTED_TYPES, key="f5")

        uploaded_files = [f for f in [file1, file2, file3, file4, file5] if f is not None]

        if len(uploaded_files) >= 1:
            if st.button("🚀 Convert, Merge & Transcribe", type="primary", key="btn_upload"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                audio_paths = []

                try:
                    VIDEO_EXTS = {".mp4", ".webm"}
                    for i, f in enumerate(uploaded_files):
                        ext = os.path.splitext(f.name)[1].lower()
                        status_text.text(f"Processing file {i + 1} of {len(uploaded_files)}: {f.name}")
                        progress_bar.progress(int((i / len(uploaded_files)) * 30))

                        if ext in VIDEO_EXTS:
                            p = convert_video_to_audio(f, "wav")
                        else:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                                tmp.write(f.read())
                                p = tmp.name
                        audio_paths.append(p)
                        cleanup_paths.append(p)

                    if len(audio_paths) > 1:
                        status_text.text("Merging audio files...")
                        progress_bar.progress(30)
                        merged_audio_path = merge_audio_files(audio_paths, "wav")
                        cleanup_paths.append(merged_audio_path)
                    else:
                        merged_audio_path = audio_paths[0]

                    progress_bar.progress(35)

                    duration = get_audio_duration(merged_audio_path)
                    if duration > 0:
                        st.info(f"Total audio duration: **{format_timestamp(duration)}**")

                    with open(merged_audio_path, "rb") as f:
                        st.download_button(
                            label="📥 Download Merged Audio (WAV)",
                            data=f,
                            file_name="merged_output.wav",
                            mime="audio/wav"
                        )

                    transcribe_progress = st.progress(0)
                    transcribe_status = st.empty()
                    paragraphs = transcribe_audio_chunked(merged_audio_path, transcribe_progress, transcribe_status)

                    transcript_with_times = "\n\n".join(paragraphs)
                    st.subheader("Transcript (smart paragraphs with timecodes)")
                    st.text_area("Transcript with Timestamps", transcript_with_times, height=400)
                    st.download_button(
                        label="📥 Download Transcript (with timecodes)",
                        data=transcript_with_times,
                        file_name="transcript_with_timecodes.txt",
                        mime="text/plain"
                    )
                    progress_bar.progress(100, text="✅ All done!")
                    status_text.empty()

                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                finally:
                    for p in cleanup_paths:
                        try:
                            os.remove(p)
                        except Exception:
                            pass
        else:
            st.info("Please upload at least 1 file.")

    else:
        # --- Local file path mode ---
        st.write("Paste the full path to a local audio/video file. No size limit — the file is read directly from disk.")
        st.caption("Example: `C:\\Users\\<you>\\Downloads\\meeting_recording.mp4`")

        local_path = st.text_input("File path:", key="local_path")

        if local_path:
            local_path = local_path.strip().strip('"').strip("'")

            if not os.path.isfile(local_path):
                st.error(f"File not found: {local_path}")
            else:
                file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
                duration = get_audio_duration(local_path)
                ext = os.path.splitext(local_path)[1].lower()

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("File Size", f"{file_size_mb:,.0f} MB")
                with col2:
                    if duration > 0:
                        st.metric("Duration", format_timestamp(duration))

                VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".avi", ".mov"}
                is_video = ext in VIDEO_EXTS

                if is_video:
                    st.info("Video file detected — audio will be extracted using ffmpeg (fast, low memory).")

                if st.button("🚀 Extract Audio & Transcribe", type="primary", key="btn_local"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        # Step 1: Extract audio if video, or use directly
                        if is_video:
                            status_text.text("Extracting audio from video with ffmpeg (this is fast)...")
                            progress_bar.progress(5)
                            audio_path = os.path.join(tempfile.gettempdir(), "extracted_audio.wav")
                            extract_audio_ffmpeg(local_path, audio_path)
                            cleanup_paths.append(audio_path)

                            extracted_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
                            st.success(f"Audio extracted: {extracted_size_mb:,.0f} MB (16kHz mono WAV)")
                        else:
                            audio_path = local_path  # use directly, don't delete

                        progress_bar.progress(15)

                        # Step 2: Show duration
                        audio_duration = get_audio_duration(audio_path)
                        if audio_duration > 0:
                            est_minutes = audio_duration / 60
                            est_transcribe = est_minutes * 0.3  # rough estimate for faster-whisper base on CPU
                            st.info(f"Audio duration: **{format_timestamp(audio_duration)}** · Estimated transcription time: ~{est_transcribe:.0f} min")

                        # Step 3: Transcribe
                        transcribe_progress = st.progress(0)
                        transcribe_status = st.empty()
                        paragraphs = transcribe_audio_chunked(audio_path, transcribe_progress, transcribe_status)

                        # Step 4: Results
                        transcript_with_times = "\n\n".join(paragraphs)
                        st.subheader("Transcript (smart paragraphs with timecodes)")
                        st.text_area("Transcript with Timestamps", transcript_with_times, height=400)
                        st.download_button(
                            label="📥 Download Transcript (with timecodes)",
                            data=transcript_with_times,
                            file_name="transcript_with_timecodes.txt",
                            mime="text/plain"
                        )
                        progress_bar.progress(100, text="✅ All done!")
                        status_text.empty()

                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                    finally:
                        for p in cleanup_paths:
                            try:
                                os.remove(p)
                            except Exception:
                                pass

# =================== TAB 2 ===================
with tab2:
    st.header("📝 Generate Minutes of Meeting from Transcript")

    # LLM Provider selection
    provider_options = ["🏠 Local (Ollama)"]
    if anthropic:
        provider_options.append("☁️ Cloud (Claude API)")
    if genai:
        provider_options.append("☁️ Cloud (Google Gemini)")
    # Always show all options even if not installed, with install hints
    if not anthropic:
        provider_options.append("☁️ Claude API (install: pip install anthropic)")
    if not genai:
        provider_options.append("☁️ Gemini (install: pip install google-genai)")

    llm_provider = st.radio("Select LLM Provider:", provider_options, horizontal=True)

    cloud_api_key = None
    cloud_model = None
    ollama_ok = False
    selected_model = "mistral"

    if llm_provider == "🏠 Local (Ollama)":
        ollama_ok = check_ollama_available()
        if not ollama_ok:
            st.warning("⚠️ Ollama is not running. Please start Ollama first (`ollama serve`) and make sure you've pulled a model (`ollama pull mistral`).")

        available_models = []
        if ollama_ok:
            try:
                model_list = ollama.list()
                available_models = [m.model for m in model_list.models] if hasattr(model_list, 'models') else []
            except Exception:
                pass

        if available_models:
            selected_model = st.selectbox("Select Ollama Model", available_models, index=0)
        else:
            selected_model = st.text_input("Ollama Model Name", value="mistral")

    elif llm_provider == "☁️ Cloud (Claude API)":
        ollama_ok = True
        cloud_api_key = st.text_input("Anthropic API Key:", type="password", help="Get your key from console.anthropic.com")
        cloud_model = st.selectbox("Select Claude Model", [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-20250414",
        ], index=0, help="Sonnet = best quality; Haiku = faster & cheaper")
        selected_model = cloud_model
        if not cloud_api_key:
            st.info("🔑 Enter your Anthropic API key above. Get one at [console.anthropic.com](https://console.anthropic.com)")

    elif llm_provider == "☁️ Cloud (Google Gemini)":
        ollama_ok = True
        cloud_api_key = st.text_input("Google AI API Key:", type="password", help="Get your free key from aistudio.google.com")
        cloud_model = st.selectbox("Select Gemini Model", [
            "gemini-3.6-flash",
            "gemini-2.5-pro",
        ], index=0, help="Flash = free & fast; Pro = higher quality")
        selected_model = cloud_model
        if not cloud_api_key:
            st.info("🔑 Enter your Google AI API key above. Get one free at [aistudio.google.com](https://aistudio.google.com)")

    else:
        st.warning("⚠️ This provider requires a Python package. Install it with the command shown, then restart the app.")

    uploaded_file = st.file_uploader("Upload your meeting transcript (.txt)", type="txt", key="momtxt")

    # Custom prompt
    default_prompt = """You are an expert at writing detailed Minutes of Meeting (MOM) for project/system design and review sessions.

From the transcript below, generate a MOM with:

1. A concise summary paragraph.
2. A detailed breakdown of all topics discussed, grouped under relevant sections such as:
    - System Design/Architecture
    - Data Sources & Integration
    - User Roles & Access Control
    - Reporting & Compliance
    - Pain Points & Challenges
    - Decisions Made
    - Action Items (with 'Who', 'What', and deadlines if possible)
3. For each section, provide concise bullet points capturing all important subpoints.
4. Clearly highlight open questions and next steps.
5. Avoid copying full sentences from the transcript. Use clear business English.

Transcript:
"""
    custom_prompt = st.text_area(
        "Enter your custom prompt for MOM summary:",
        value=default_prompt,
        height=250
    )

    # Chunking option
    chunk_mode = st.radio(
        "Split transcript into chunks? (recommended for long transcripts)",
        ("No", "Yes"),
        index=0
    )

    if chunk_mode == "Yes":
        chunk_size = st.number_input("Chunk size (words per chunk):", min_value=500, max_value=5000, value=2000, step=500)
    else:
        chunk_size = None

    # --- Helper: call LLM (Ollama, Claude, or Gemini) ---
    def call_llm(system_msg, user_msg):
        """Call the selected LLM provider and return the response text."""
        if llm_provider == "☁️ Cloud (Claude API)":
            client = anthropic.Anthropic(api_key=cloud_api_key)
            response = client.messages.create(
                model=cloud_model,
                max_tokens=4096,
                system=system_msg,
                messages=[{"role": "user", "content": user_msg}]
            )
            return response.content[0].text
        elif llm_provider == "☁️ Cloud (Google Gemini)":
            client = genai.Client(api_key=cloud_api_key)
            response = client.models.generate_content(
                model=cloud_model,
                contents=f"{system_msg}\n\n{user_msg}"
            )
            return response.text
        else:
            response = ollama.chat(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ]
            )
            return response['message']['content']

    if uploaded_file is not None:
        text = uploaded_file.read().decode('utf-8')
        word_count = len(text.split())
        st.info(f"Transcript loaded: **{word_count:,} words**")
        st.text_area("Original Transcript", text, height=200)

        if st.button("🚀 Generate MOM", type="primary"):
            # Validation
            if llm_provider == "🏠 Local (Ollama)" and not ollama_ok:
                st.error("Ollama is not running. Please start it first.")
            elif llm_provider in ("☁️ Cloud (Claude API)", "☁️ Cloud (Google Gemini)") and not cloud_api_key:
                st.error("Please enter your Anthropic API key above.")
            else:
                try:
                    import time as _time
                    if llm_provider == "☁️ Cloud (Claude API)":
                        provider_label = f"Claude ({cloud_model})"
                    elif llm_provider == "☁️ Cloud (Google Gemini)":
                        provider_label = f"Gemini ({cloud_model})"
                    else:
                        provider_label = f"Ollama ({selected_model})"

                    if chunk_mode == "Yes":
                        chunks = split_text_into_chunks(text, chunk_size)
                        chunk_summaries = []
                        progress = st.progress(0, text="Processing chunks...")
                        time_info = st.empty()
                        chunk_times = []
                        for idx, chunk in enumerate(chunks):
                            chunk_start = _time.time()
                            if chunk_times:
                                avg_time = sum(chunk_times) / len(chunk_times)
                                remaining = avg_time * (len(chunks) - idx)
                                mins, secs = divmod(int(remaining), 60)
                                time_info.info(f"⏱️ [{provider_label}] Avg {avg_time:.0f}s/chunk · Est. remaining: **{mins}m {secs}s** ({len(chunks) - idx} chunks left)")
                            else:
                                time_info.info(f"⏱️ [{provider_label}] Processing chunk 1 of {len(chunks)}... (estimating time after first chunk)")
                            progress.progress(
                                int((idx / len(chunks)) * 80),
                                text=f"Processing chunk {idx + 1} of {len(chunks)}..."
                            )
                            mom = call_llm("You are an expert MOM summarizer.", custom_prompt + chunk)
                            chunk_summaries.append(mom)
                            chunk_times.append(_time.time() - chunk_start)

                        # Show chunk summaries
                        st.subheader("Chunk Summaries")
                        for idx, chunk_mom in enumerate(chunk_summaries):
                            with st.expander(f"Chunk {idx + 1} Summary"):
                                st.markdown(chunk_mom)

                        # Merge
                        progress.progress(85, text="Merging chunk summaries into final MOM...")
                        merge_prompt = f"""Below are MOM summaries for different sections (chunks) of a meeting transcript. Please synthesize them into a single, coherent, well-structured Minutes of Meeting (MOM) as if you listened to the whole meeting:

{chr(10).join([f"Chunk {i+1}: {summary}" for i, summary in enumerate(chunk_summaries)])}

Write a complete MOM including summary paragraph, key topics, decisions, action items, and clear structure (no duplication).
"""
                        final_mom = call_llm("You are an expert MOM synthesizer.", merge_prompt)
                        progress.progress(100, text="✅ MOM generated!")

                        st.subheader("Final Synthesized Minutes of Meeting (MOM)")
                        st.markdown(final_mom)
                        st.download_button(
                            label="📥 Download Final MOM",
                            data=final_mom,
                            file_name="final_meeting_mom.txt",
                            mime="text/plain"
                        )
                    else:
                        status_msg = st.empty()
                        status_msg.info(f"⏳ Generating MOM with {provider_label}... (single pass, no chunking)")
                        start_time = _time.time()

                        mom = call_llm("You are an expert MOM summarizer.", custom_prompt + text)

                        elapsed = _time.time() - start_time
                        mins, secs = divmod(int(elapsed), 60)
                        status_msg.success(f"✅ MOM generated in **{mins}m {secs}s** using {provider_label}")

                        st.subheader("Minutes of Meeting (MOM)")
                        st.markdown(mom)
                        st.download_button(
                            label="📥 Download MOM",
                            data=mom,
                            file_name="meeting_mom.txt",
                            mime="text/plain"
                        )
                except Exception as e:
                    err_str = str(e).lower()
                    if "authentication" in err_str or "api key" in err_str or "invalid" in err_str:
                        st.error("❌ Invalid API key. Please check your key and try again.")
                    elif "rate" in err_str or "quota" in err_str:
                        st.error("⏳ Rate limit or quota reached. Please wait a moment and try again.")
                    elif "credit" in err_str or "billing" in err_str:
                        st.error("💳 Insufficient credits/billing issue. Check your account balance.")
                    else:
                        st.error(f"Error generating MOM: {str(e)}")
