from __future__ import annotations

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import Settings


class LLMFactory:
    @staticmethod
    def build_chat_model(settings: Settings) -> ChatGoogleGenerativeAI | None:
        if not settings.google_api_key:
            return None

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.2,
            max_retries=2,
        )


def extract_text(response: Any) -> str:
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
                elif item.get("type") == "thinking":
                    continue
                else:
                    text_parts.append(str(item))
            else:
                text_parts.append(str(item))
        return "\n".join(part for part in text_parts if part).strip()
    return str(content).strip()
