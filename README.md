# PS3/BS3 Functional Evidence Analysis Pipeline

A comprehensive pipeline for evaluating ACMG functional criteria PS3 and BS3 for genetic variants using LitVar2, PubMed, and LLM-based evidence extraction.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run analysis
python main.py --chrom 2 --pos 162279995 --ref C --alt G
```

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [ACMG Criteria](#acmg-criteria)
- [API Documentation](#api-documentation)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Installation

### Requirements
- Python 3.8+
- pip or conda

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install requests langchain-core metapub python-dotenv

# Choose one or more LLM providers:
pip install langchain-openai              # OpenAI
pip install langchain-anthropic           # Anthropic
pip install langchain-google-genai         # Google Gemini
```

---

## Configuration

### 1. Create Environment File

```bash
cp .env.example .env
```

### 2. Choose LLM Provider

#### OpenAI (Recommended)
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
LLM_MODEL=gpt-4o-mini
```
Get key from: https://platform.openai.com/api-keys

#### Anthropic Claude
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
LLM_MODEL=claude-3-5-sonnet-20241022
```
Get key from: https://console.anthropic.com/

#### Google Gemini
```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-google-api-key
LLM_MODEL=gemini-1.5-flash
```
Get key from: https://makersuite.google.com/app/apikey

### 3. Add NCBI Credentials (Required)

```env
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=your-ncbi-api-key    # Optional, improves rate limits
```

### 4. Optional Settings

```env
LLM_TEMPERATURE=0                  # 0 = deterministic, 1 = random
```

---

## Usage

### Command Line Interface

#### Basic Analysis (Default: HTML Report)
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G
```

#### Required Arguments
```
--chrom CHROM          Chromosome (1, 2, ..., X, MT)
--pos POS              Genomic position (1-based integer)
--ref REF              Reference allele
--alt ALT              Alternate allele
```

#### Optional Arguments
```
--assembly {GRCh38,GRCh37}  Genome assembly (default: GRCh38)
--model MODEL               Override LLM model from .env
--pdf-path PATH             Directory for PDF downloads (default: func_papers_pdf)
--output-format {html,dict} Output format (default: html)
--output-dir PATH           Output directory (default: output_report)
```

#### CLI Examples

**Different Genome Assembly**
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G --assembly GRCh37
```

**Custom LLM Model**
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G \
               --model claude-3-5-sonnet-20241022
```

**Dictionary Output (for scripts)**
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G \
               --output-format dict > results.json
```

**Custom Directories**
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G \
               --output-dir reports \
               --pdf-path papers/downloaded_pdfs
```

**All Options**
```bash
python main.py \
  --chrom 17 --pos 41244694 --ref T --alt A \
  --assembly GRCh38 \
  --model gpt-4o-mini \
  --pdf-path papers \
  --output-format html \
  --output-dir analysis_results
```

**Get Help**
```bash
python main.py --help
```

### Python API

```python
from main import analyze_variant

# Run analysis
result = analyze_variant(
    chrom="2",
    pos=162279995,
    ref="C",
    alt="G",
    assembly="GRCh38",
    pdf_path="papers"
)

# Access results
decision = result["assessment"]["decision"]      # "PS3", "BS3", or "none"
strength = result["assessment"]["strength"]      # "strong" or "supporting"
narrative = result["assessment"]["narrative"]    # Detailed explanation

print(f"Decision: {decision}")
print(f"Narrative: {narrative}")

# Process experiments
for exp in result["experiments"]:
    print(f"PMID {exp['pmid']}: {exp['assay_type']}")
```

### Batch Analysis

```python
from main import analyze_variant
import json

variants = [
    {"chrom": "2", "pos": 162279995, "ref": "C", "alt": "G"},
    {"chrom": "17", "pos": 41244694, "ref": "T", "alt": "A"},
]

results = {}
for variant in variants:
    key = f"{variant['chrom']}:{variant['pos']}"
    results[key] = analyze_variant(**variant)

# Save results
with open("batch_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
```

---

## Project Structure

```
LLM_PS3_BS3/
├── main.py                  # CLI entry point
├── examples.py              # Python usage examples
├── requirements.txt         # Dependencies
├── .env.example             # Configuration template
├── .env                     # Configuration (git-ignored)
├── .gitignore               # Git ignore patterns
├── README.md                # This file
│
├── src/
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration loading
│   ├── llm.py               # Multi-provider LLM support
│   ├── utils.py             # Data classes and utilities
│   ├── vep.py               # VEP annotation
│   ├── litvar2.py           # LitVar2 and PubMed retrieval
│   ├── filtering.py         # LLM-based filtering
│   ├── assessment.py        # PS3/BS3 decision logic
│   ├── html_report.py       # HTML report generation
│   └── reporting.py         # Console reporting
│
└── notebooks/               # Jupyter notebooks (optional)
```

### Module Descriptions

| Module | Purpose |
|--------|---------|
| **main.py** | CLI entry point with argument parsing |
| **src/config.py** | Environment variable configuration and validation |
| **src/llm.py** | Multi-provider LLM initialization (OpenAI, Anthropic, Gemini) |
| **src/utils.py** | Data classes: VariantInfo, CandidatePaper, FunctionalPaper, etc. |
| **src/vep.py** | Ensembl VEP REST API integration for variant annotation |
| **src/litvar2.py** | LitVar2 and PubMed literature retrieval |
| **src/filtering.py** | LLM-based paper filtering and experiment extraction |
| **src/assessment.py** | Evidence integration and PS3/BS3 decision logic |
| **src/html_report.py** | HTML report generation with professional styling |
| **src/reporting.py** | Console report formatting and output |

---

## ACMG Criteria

### PS3 (Pathogenic - Strong)
Well-established in vitro or in vivo functional studies supportive of a damaging effect on the gene or gene product.

**Indicators:**
- Impaired enzyme activity
- Reduced protein expression
- Abnormal splicing
- Loss of protein-protein interactions

### BS3 (Benign - Strong)
Well-established in vitro or in vivo functional studies show no damaging effect on protein function or splicing.

**Indicators:**
- Normal enzyme activity
- Normal protein expression
- Normal splicing
- Maintained protein-protein interactions

---

## Output Formats

### 1. HTML Report (Default)
```
output_report/2_162279995_C_G_GRCh38.html
```
- Professional, interactive web page
- Contains all analysis results
- Mobile-responsive design
- Viewable in any web browser
- Easy to share and archive

### 2. Dictionary Format
```json
{
  "variant_info": {
    "chrom": "2",
    "pos": 162279995,
    "ref": "C",
    "alt": "G",
    "gene_symbol": "...",
    "rsid": "...",
    "hgvsc": "...",
    "hgvsp": "..."
  },
  "candidate_papers": [...],
  "functional_papers": [...],
  "experiments": [...],
  "assessment": {
    "decision": "PS3",
    "strength": "strong",
    "narrative": "..."
  }
}
```
- Printed to stdout as JSON
- Can be saved to file: `python main.py ... --output-format dict > results.json`
- Suitable for programmatic processing

### 3. PDF Downloads (Optional)
```
func_papers_pdf/
├── 12345678.pdf
├── 23456789.pdf
└── ...
```
- Automatically downloaded from PubMed Central or publisher links
- Useful for manual review
- Location customizable via `--pdf-path` argument

---

## API Documentation

### analyze_variant()

```python
def analyze_variant(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    assembly: str = "GRCh38",
    pdf_path: Optional[str] = None,
) -> Dict[str, Any]:
```

**Parameters:**
- `chrom` (str): Chromosome (e.g., "1", "2", "X")
- `pos` (int): Genomic position (1-based)
- `ref` (str): Reference allele
- `alt` (str): Alternate allele
- `assembly` (str): Genome assembly version (default: "GRCh38")
- `pdf_path` (str, optional): Directory to save functional paper PDFs

**Returns:**
- Dictionary with keys: `variant_info`, `candidate_papers`, `functional_papers`, `experiments`, `assessment`

**Example:**
```python
result = analyze_variant("2", 162279995, "C", "G")
print(result["assessment"]["decision"])
```

---

## Examples

See `examples.py` for 6 complete Python examples:

1. Simple variant analysis
2. Using different LLM model (Claude)
3. Batch analysis of multiple variants
4. Custom HTML report generation
5. Extracting specific data
6. Analyzing with different genome assemblies

Run examples:
```bash
python examples.py
```

---

## Workflow

The pipeline follows this automated workflow:

```
1. VEP Annotation
   ↓
   Query Ensembl VEP for: rsID, HGVSc, HGVSp, gene symbol

2. LitVar2 Query
   ↓
   Search LitVar2 for papers mentioning the variant

3. PubMed Retrieval
   ↓
   Fetch paper metadata (title, abstract) from PubMed

4. LLM Filtering
   ↓
   Use LLM to identify papers with functional experiments

5. Experiment Extraction
   ↓
   Extract detailed experiment information using LLM

6. Evidence Integration
   ↓
   Consolidate experiments and make PS3/BS3 call

7. Report Generation
   ↓
   Generate HTML report and/or dictionary output
```

---

## Supported LLM Providers

| Provider | Models | Speed | Cost |
|----------|--------|-------|------|
| **OpenAI** | gpt-4o, gpt-4-turbo, gpt-4o-mini | Fast | Moderate |
| **Anthropic** | claude-3-opus, claude-3-sonnet, claude-3-haiku | Moderate | Moderate |
| **Google Gemini** | gemini-1.5-pro, gemini-1.5-flash | Fast | Low |

Recommended: **gpt-4o-mini** (fast and cost-effective)

---

## Environment Variables

### Required
- `OPENAI_API_KEY` (if using OpenAI)
- `ANTHROPIC_API_KEY` (if using Anthropic)
- `GOOGLE_API_KEY` (if using Gemini)
- `NCBI_EMAIL`

### Optional
- `NCBI_API_KEY` - Increases NCBI rate limits
- `LLM_TEMPERATURE` - Randomness (0-1, default: 0)
- `LLM_PROVIDER` - Provider choice (default: openai)
- `LLM_MODEL` - Model override

---

## Troubleshooting

### API Key Errors

**Error:** `OPENAI_API_KEY not found`
- **Solution:** Ensure `.env` file exists in project root with correct API key

**Error:** `ANTHROPIC_API_KEY not found` when using Claude
- **Solution:** Set `LLM_PROVIDER=anthropic` and provide `ANTHROPIC_API_KEY` in `.env`

### Import Errors

**Error:** `Import "langchain_openai" could not be resolved`
- **Solution:** Install dependencies: `pip install -r requirements.txt`

### Literature Not Found

**Error:** No papers found in LitVar2
- **Solution:** Normal for some variants. Try alternate variant identifiers (rsID, HGVSc, HGVSp)

### HTML Generation Fails

**Error:** Failed to generate HTML report
- **Solution:** Use `--output-format dict` instead, or check browser can open HTML files

### Timeout Issues

**Error:** API timeout or no response
- **Solution:** Try again later, check internet connection, verify APIs are accessible

---

## Performance Tips

1. **First run is slower** due to API calls and PDF downloads
2. **Model selection affects speed/accuracy**:
   - Fast: gemini-1.5-flash
   - Balanced: gpt-4o-mini
   - Most accurate: claude-3-opus
3. **Batch processing**: Create scripts to analyze multiple variants
4. **Cache results**: Save HTML reports for documentation

---

## Security Notes

- ⚠️ **Never commit `.env` file** - contains sensitive API keys
- Use `.env.example` as template for other developers
- `.gitignore` is configured to exclude `.env` files
- Keep all API keys confidential

---

## Contributing

To extend the pipeline:

1. Add new modules to `src/`
2. Update `src/__init__.py` if adding exports
3. Ensure all modules have docstrings
4. Test with multiple variants
5. Document changes in README

---

## License

[Add your license here]

---

## Citation

If you use this pipeline in research, please cite:

```
AcmGENTIC: PS3/BS3 Functional Evidence Analysis Pipeline
Available at: https://github.com/AliSaadatV/AcmGENTIC
```

---

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review examples in `examples.py`
3. Check `.env` configuration
4. Review error messages carefully
5. Open an issue on GitHub

---

## Changelog

### v1.0.0 (Current)
- Initial release
- Multi-provider LLM support (OpenAI, Anthropic, Gemini)
- HTML report generation
- Command-line interface with argument parsing
- Batch analysis capabilities
- Python API for programmatic use
