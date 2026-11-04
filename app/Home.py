import streamlit as st

st.set_page_config(page_title="MoM Toolbox", page_icon="📑", layout="centered")

pages = [
    st.Page("recorder_page.py", title="System Audio Recorder", icon="🎙️", default=True),
    st.Page("mom_page.py", title="Transcript & MoM", icon="📑"),
]

st.navigation(pages).run()
