"""
Configuration and environment variables for PS3/BS3 analysis pipeline.

Load environment variables from .env file using python-dotenv.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# NCBI / Entrez
NCBI_API_KEY = os.getenv("NCBI_API_KEY")
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "your_email@example.com")

# LLM configuration via LangChain
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# Provider-specific model defaults
_PROVIDER_DEFAULTS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-1.5-flash",
}

LLM_MODEL = os.getenv("LLM_MODEL", _PROVIDER_DEFAULTS.get(LLM_PROVIDER, "gpt-4o-mini"))

# API endpoints
LITVAR2_API_BASE = "https://www.ncbi.nlm.nih.gov/research/litvar2-api"
ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"

# Validate required API keys based on provider
if LLM_PROVIDER == "openai":
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY environment variable must be set in .env file, e.g.:\n"
            "export OPENAI_API_KEY='sk-...'"
        )
elif LLM_PROVIDER == "anthropic":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable must be set in .env file, e.g.:\n"
            "export ANTHROPIC_API_KEY='sk-ant-...'"
        )
elif LLM_PROVIDER == "gemini":
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError(
            "GOOGLE_API_KEY environment variable must be set in .env file, e.g.:\n"
            "export GOOGLE_API_KEY='your-google-api-key'"
        )
else:
    raise ValueError(
        f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. "
        "Supported providers: openai, anthropic, gemini"
    )
