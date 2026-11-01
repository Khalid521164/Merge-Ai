"""Canonical public facts about Merge AI, not the visiting user's identity."""
from __future__ import annotations
import re

PROJECT_NAME = "Merge AI"
CREATOR_NAME = "Khalid Bin Ashraf"
OWNER_NAME = "Khalid Bin Ashraf"
CREATED_FOR = "a seventh-grade science fair project"
PURPOSE = (
    "Khalid created Merge AI to explore whether answers from multiple AI "
    "providers could be combined into one useful response. He also wanted "
    "people to have an easy-to-use assistant with web research, "
    "account-based chat history, and personal memory."
)
PROVIDERS = "Gemini, Groq, and OpenRouter"
PROJECT_WEBSITE = "https://mergeai.streamlit.app/"

PROJECT_CONTEXT = (
    f"You are {PROJECT_NAME}. Your creator and project owner is {CREATOR_NAME}. "
    f"You started as {CREATED_FOR}. {PURPOSE} "
    f"Your AI providers include {PROVIDERS}. "
    "These are facts about the project, not facts about the person chatting. "
    "Never claim a visitor is your creator unless separately verified."
)

def answer_project_question(question: str) -> str | None:
    """Answer direct questions about the creator or why Merge AI exists."""
    q = re.sub(r"\s+", " ", str(question).casefold()).strip()
    about = bool(re.search(r"\b(?:merge ai|mergeai|you|your|this ai|this app)\b", q))
    creator = bool(re.search(
        r"\b(?:who\s+(?:made|created|built|owns|developed)|"
        r"who(?:'s| is)\s+(?:your|the)\s+(?:creator|owner)|"
        r"your\s+(?:creator|owner)|who\s+is\s+khalid)\b", q
    ))
    purpose = bool(re.search(
        r"\b(?:why\s+(?:were|was|did|is)|"
        r"what\s+is\s+(?:your|the)\s+(?:purpose|goal)|"
        r"why\s+create|reason\s+(?:for|behind))\b", q
    ))
    if about and creator and purpose:
        return f"I was created by **{CREATOR_NAME}** for {CREATED_FOR}. {PURPOSE}"
    if about and creator:
        return f"**{CREATOR_NAME}** created Merge AI and is its project owner."
    if about and purpose:
        return f"I was created by **{CREATOR_NAME}** for {CREATED_FOR}. {PURPOSE}"
    return None
