# PS3/BS3 Functional Evidence Analysis Pipeline

A comprehensive pipeline for evaluating ACMG functional criteria PS3 and BS3 for genetic variants using LitVar2, PubMed, and LLM-based evidence extraction.

## Project Structure

```
.
├── main.py              # Main entry point - run with: python main.py
├── .env.example         # Example environment variables
├── .env                 # Your actual environment variables (add to .gitignore)
├── .gitignore           # Git ignore file
├── README.md            # This file
├── QUICKSTART.md        # Quick start guide
├── src/
│   ├── __init__.py      # Package initialization
│   ├── config.py        # Configuration and environment variables
│   ├── utils.py         # Common data classes and utility functions
│   ├── vep.py           # Ensembl VEP annotation functionality
│   ├── litvar2.py       # LitVar2 and PubMed literature retrieval
│   ├── filtering.py     # LLM-based paper filtering and experiment extraction
│   ├── assessment.py    # Evidence integration and PS3/BS3 decision logic
│   ├── reporting.py     # Report generation and formatting
│   └── main.py          # Pipeline functions (orchestration)
├── notebooks/           # Jupyter notebooks for interactive analysis
└── tests/               # Unit tests (optional)
```

## Module Descriptions

### `main.py` (Root)
Main entry point script. Run with `python main.py` from the project root.

### `src/config.py`
Handles configuration via environment variables loaded from `.env`:
- NCBI API credentials
- LLM provider and model settings
- API endpoints for LitVar2, Entrez, and EuropePMC

### `src/utils.py`
Common data structures and utilities:
- `VariantInfo` - Stores variant coordinates and annotations
- `CandidatePaper` - Paper metadata from LitVar2
- `FunctionalPaper` - Confirmed functional papers
- `FunctionalExperiment` - Extracted experiment details
- `IntegratedAssessment` - Final PS3/BS3 decision
- Helper functions: `build_variant_label()`, `enrich_with_vep()`

### `src/vep.py`
VEP annotation via Ensembl REST API:
- `vep_annotate_variant()` - Queries Ensembl VEP for rsID, HGVSc, HGVSp, gene symbol

### `src/litvar2.py`
Literature retrieval:
- `query_litvar2()` - Searches LitVar2 for variant mentions
- `query_litvar2_publications()` - Gets PMIDs for specific variant IDs
- `pubmed_fetch_details()` - Fetches full paper metadata from PubMed
- `build_candidate_list()` - Assembles candidate papers

### `src/filtering.py`
LLM-based filtering and extraction:
- `llm_filter_functional_papers()` - Uses LLM to identify papers with functional experiments
- `llm_extract_experiments()` - Extracts detailed experiment information
- `fetch_full_text_or_abstract()` - Retrieves full PubMed text

### `src/assessment.py`
Evidence integration logic:
- `integrate_evidence()` - Consolidates experiments and makes PS3/BS3 call
- Decision logic based on experiment quality and quantity

### `src/reporting.py`
Output formatting:
- `print_report()` - Generates comprehensive analysis report

### `src/main.py`
Pipeline orchestration:
- `analyze_variant()` - Main function that coordinates all steps

## Usage

### From Command Line (Recommended)

```bash
python main.py
```

### From Python

```python
from src.main import analyze_variant

result = analyze_variant(
    chrom="2",
    pos=162279995,
    ref="C",
    alt="G"
)

print(result["assessment"]["decision"])
```

### Interactive Jupyter Notebooks

```bash
jupyter notebook notebooks/
```

## Environment Setup

### 1. Copy the example environment file:

```bash
cp .env.example .env
```

### 2. Edit `.env` with your credentials:

```
OPENAI_API_KEY=sk-your-api-key-here
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=your-ncbi-api-key  # optional
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0
```

### 3. Install dependencies:

```bash
pip install requests langchain-openai langchain-core metapub python-dotenv
```

## ACMG Criteria

### PS3 (Pathogenic - Strong)
Well-established in vitro or in vivo functional studies supportive of a damaging effect on the gene or gene product.

### BS3 (Benign - Strong)
Well-established in vitro or in vivo functional studies show no damaging effect on protein function or splicing.

## Output

The pipeline returns a dictionary containing:
- `variant_info` - VEP-annotated variant details
- `candidate_papers` - All papers found by LitVar2
- `functional_papers` - Papers with experimental functional data
- `experiments` - Extracted experiment details
- `assessment` - Final PS3/BS3 decision and narrative

## Security

- **Never commit `.env` file to git** - it contains sensitive API keys
- Use `.env.example` as a template for configuration
- `.gitignore` is configured to exclude `.env` files
- Load environment variables from `.env` using `python-dotenv`
