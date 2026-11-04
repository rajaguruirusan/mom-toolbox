"""Shared state for SystemAudioRecorder — lives in a separate module
so Python's import cache preserves it across Streamlit reruns."""
import threading

stop_event = threading.Event()
result_lock = threading.Lock()
result_file = [None]  # mutable container: [path_string or None]
