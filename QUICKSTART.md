# Quick Start Guide

## Installation

1. Ensure you have all dependencies installed:
```bash
pip install requests langchain-openai langchain-core metapub python-dotenv
```

2. Set up environment variables:
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your credentials
# OPENAI_API_KEY=sk-your-key-here
# NCBI_EMAIL=your-email@example.com
# etc.
```

## Running the Pipeline

### From Command Line (Recommended)

```bash
python main.py
```

This will run the example variant (2:162279995 C>G) using credentials from `.env`.

### From Python

```python
from src.main import analyze_variant

# Analyze a variant
result = analyze_variant(
    chrom="2",
    pos=162279995,
    ref="C",
    alt="G",
    assembly="GRCh38"
)

# Access results
print(result["assessment"]["decision"])  # "PS3", "BS3", or "none"
print(result["assessment"]["narrative"])
```

## File Organization

- **src/** - All source code
  - `config.py` - Global settings
  - `utils.py` - Data classes and helpers
  - `vep.py` - VEP annotation
  - `litvar2.py` - Literature search
  - `filtering.py` - LLM-based filtering
  - `assessment.py` - PS3/BS3 decision logic
  - `reporting.py` - Report generation
  - `main.py` - Main pipeline
  - `__init__.py` - Package exports

- `notebooks/` - Jupyter notebooks for interactive analysis
- `README.md` - Full documentation

## Output

The pipeline generates:

1. **Console Report** - Formatted analysis with:
   - Variant identifiers
   - Literature summary
   - Functional papers identified
   - Experiment details
   - PS3/BS3 decision and strength

2. **Dictionary Result** containing:
   - Variant annotations
   - Paper metadata
   - Experiment details
   - Assessment with decision and narrative

## Typical Workflow

1. User provides variant coordinates (CHR:POS REF>ALT)
2. VEP annotation enriches variant with rsID, HGVSc, HGVSp, gene symbol
3. Multiple variant identifiers queried in LitVar2
4. PubMed fetches metadata for all candidate papers
5. LLM filters for papers with functional experiments
6. LLM extracts detailed experiment information
7. Assessment logic determines PS3/BS3 applicability
8. Report generated with decision and supporting evidence
