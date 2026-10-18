import streamlit as st
from merge_ai import MergeAI, default_providers

st.set_page_config(
    page_title="Merge AI",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 Merge AI")
st.caption("Gemini + OpenRouter + Groq")

# Keep one AI session while the website is open
if "engine" not in st.session_state:
    st.session_state.engine = MergeAI(
        providers=default_providers()
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

# Show previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask Merge AI something...")

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Merge AI is thinking..."):
            try:
                answer = st.session_state.engine.ask(question)
            except Exception:
                answer = "Merge AI could not answer right now. Please check Settings."

        st.markdown(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
    })