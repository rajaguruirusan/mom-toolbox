import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser


def resource_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def free_port(start=8501, end=8600):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def open_browser_when_ready(url, port):
    for _ in range(600):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                time.sleep(1)
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def main():
    app_script = os.path.join(resource_dir(), "app", "Home.py")
    port = free_port()
    url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print(" MoM Toolbox is starting...")
    print(f" If the browser does not open, go to: {url}")
    print(" Keep this window open while using the app.")
    print(" Close this window to quit MoM Toolbox.")
    print("=" * 60)

    threading.Thread(target=open_browser_when_ready, args=(url, port), daemon=True).start()

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        app_script,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=viewer",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
