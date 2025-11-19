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
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# API endpoints
LITVAR2_API_BASE = "https://www.ncbi.nlm.nih.gov/research/litvar2-api"
ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"

# Validate required environment variables
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY environment variable must be set in .env file or exported, e.g.:\n"
        "export OPENAI_API_KEY='sk-...'"
    )
