import os
import streamlit as st

for key in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "TAVILY_API_KEY",
            "GEMINI_MODEL", "OPENROUTER_MODEL", "GROQ_MODEL"):
    if key in st.secrets:
        os.environ[key] = str(st.secrets[key])

from merge_ai import MergeAI, default_providers

st.set_page_config(page_title="Merge AI", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
.stApp { background:#10141d; color:#edf2f7; font-family:'DM Sans',sans-serif; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { background:#151b26; border-right:1px solid #273142; }
[data-testid="stSidebar"] * { color:#cbd5e1; }
.top { display:flex; align-items:center; justify-content:space-between; padding:8px 0 36px; border-bottom:1px solid #273142; margin-bottom:42px; }
.brand { display:flex; align-items:center; gap:12px; }
.logo { width:40px; height:40px; border-radius:12px; display:grid; place-items:center; font-size:21px; color:#fff; background:linear-gradient(135deg,#6d5dfc,#19c6b7); box-shadow:0 8px 24px #6d5dfc44; }
.brand h1 { font:700 21px 'Space Grotesk'; margin:0; color:#fff; letter-spacing:-.4px; }
.brand small { color:#8995a8; font-size:12px; }
.status { color:#89e7c9; font-size:12px; background:#17342f; border:1px solid #285c52; border-radius:99px; padding:7px 11px; }
.content { max-width:920px; margin:auto; padding:24px 24px 120px; }
.hero { max-width:650px; margin:0 auto 44px; text-align:center; }
.hero h2 { font:600 45px/1.08 'Space Grotesk'; letter-spacing:-2px; margin:0 0 15px; color:#fff; }
.hero h2 em { font-style:normal; color:#63d9cb; }
.hero p { color:#9aa7b8; font-size:16px; margin:0; }
.cards { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:28px; }
.card { background:#171e2a; border:1px solid #293445; border-radius:15px; padding:16px; }
.card b { display:block; color:#fff; font-size:14px; margin-bottom:5px; }
.card span { color:#8995a8; font-size:12px; }
.dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#63d9cb; margin-right:7px; }
.empty { border:1px dashed #354256; border-radius:18px; padding:28px; text-align:center; color:#8995a8; margin-bottom:18px; }
.empty b { color:#e8edf5; display:block; margin-bottom:6px; }
.stChatMessage { border:0; padding:14px 0; }
[data-testid="stChatMessageContent"] { border-radius:16px; padding:14px 18px; }
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] { background:#223149; }
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stChatMessageContent"] { background:#171e2a; border:1px solid #293445; }
[data-testid="stChatInput"] { background:#171e2a; border:1px solid #354256; border-radius:17px; }
footer { visibility:hidden; }
@media(max-width:700px) { .cards { grid-template-columns:1fr; } .hero h2 { font-size:34px; } .content { padding:16px 12px 100px; } .status { display:none; } }
</style>
""", unsafe_allow_html=True)

if "engine" not in st.session_state:
    st.session_state.engine = MergeAI(providers=default_providers(), tavily_api_key=os.environ.get("TAVILY_API_KEY", ""))
if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown('<div class="content">', unsafe_allow_html=True)
st.markdown('<div class="top"><div class="brand"><div class="logo">✦</div><div><h1>Merge AI</h1><small>Research, compare, answer</small></div></div><div class="status"><span class="dot"></span>Ready to chat</div></div>', unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown('<div class="hero"><h2>One question.<br><em>Three minds. One answer.</em></h2><p>Merge AI combines leading models and web research into a clear response you can trust.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="cards"><div class="card"><b>◈ Gemini</b><span>Reasoning and context</span></div><div class="card"><b>◉ OpenRouter</b><span>Model comparison</span></div><div class="card"><b>⌁ Groq</b><span>Fast responses</span></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="empty"><b>Start a conversation</b>Ask anything below and Merge AI will prepare the final answer.</div>', unsafe_allow_html=True)

for item in st.session_state.messages:
    with st.chat_message(item["role"], avatar="✦" if item["role"] == "assistant" else "You"):
        st.markdown(item["content"])

question = st.chat_input("Message Merge AI…")
if question:
    st.session_state.messages.append({"role":"user", "content":question})
    with st.chat_message("user", avatar="You"):
        st.markdown(question)
    with st.chat_message("assistant", avatar="✦"):
        with st.spinner("Comparing models and researching…"):
            try:
                answer = st.session_state.engine.ask(question)
            except Exception:
                answer = "I could not complete that answer right now. Please try again."
        st.markdown(answer)
    st.session_state.messages.append({"role":"assistant", "content":answer})

st.markdown('</div>', unsafe_allow_html=True)
