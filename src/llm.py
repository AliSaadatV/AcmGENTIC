"""
LLM provider initialization and management.

Supports multiple LLM providers: OpenAI, Anthropic, and Google Gemini.
"""

from typing import Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from .config import LLM_PROVIDER, LLM_MODEL, LLM_TEMPERATURE


def get_llm() -> Any:
    """
    Initialize and return the appropriate LLM based on LLM_PROVIDER config.

    Supported providers:
    - openai: Uses ChatOpenAI with gpt-4o-mini by default
    - anthropic: Uses ChatAnthropic with Claude models
    - gemini: Uses ChatGoogleGenerativeAI with Gemini models

    Returns
    -------
    Any
        Initialized LLM instance with JSON response format
    """
    if LLM_PROVIDER == "openai":
        return ChatOpenAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    elif LLM_PROVIDER == "anthropic":
        # Anthropic requires model names like "claude-3-5-sonnet-20241022"
        return ChatAnthropic(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
        )

    elif LLM_PROVIDER == "gemini":
        # Gemini requires a different approach for JSON responses
        return ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {LLM_PROVIDER}. "
            "Supported providers: openai, anthropic, gemini"
        )


# Initialize LLM on module import
LLM = get_llm()
