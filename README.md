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
- [Agentic Extraction](#agentic-extraction)
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
pip install langchain-openai openai                    # OpenAI
pip install langchain-anthropic anthropic              # Anthropic
pip install langchain-google-genai google-generativeai # Google Gemini
```

### PDF Report Generation (Optional)

PDF output requires WeasyPrint, which has system library dependencies:

**macOS:**
```bash
brew install cairo pango gdk-pixbuf libffi
pip install weasyprint
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
pip install weasyprint
```

**Windows:**
See [WeasyPrint Windows installation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)

**Note:** PDF generation is optional. The pipeline will still generate HTML reports if WeasyPrint is not installed.

### Agentic Extraction Dependencies (Optional)

For advanced agentic document extraction with OCR and visual analysis:

**System Dependencies (pdf2image requires poppler):**
```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Windows
# Download from https://github.com/oschwartz10612/poppler-windows/releases
```

**Python Dependencies:**
```bash
# Core agentic dependencies
pip install pdf2image Pillow opencv-python transformers torch layoutreader

# OCR - choose one:
pip install easyocr          # Recommended for macOS (more stable)
pip install paddleocr paddlepaddle  # Alternative (may have issues on macOS)
```

---

## Configuration

### 1. Create Environment File

```bash
cp .env.example .env
```

### 2. Choose LLM Provider

#### OpenAI 
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

# Agentic extraction settings
USE_AGENTIC_EXTRACTION=false       # Enable agentic extraction by default
AGENTIC_VLM_MODEL=gpt-4o-mini      # Vision model for table/chart analysis
                                   # Use gpt-4o for better accuracy
USE_PADDLEOCR=false                # Force PaddleOCR instead of EasyOCR on macOS
```

---

## Usage

### Command Line Interface

#### Basic Analysis (Default: HTML + PDF Report)
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
--assembly {GRCh38,GRCh37}          Genome assembly (default: GRCh38)
--model MODEL                       Override LLM model from .env
--pdf-path PATH                     Directory for PDF downloads (default: func_papers_pdf)
--output-format {html,pdf,both,dict} Output format (default: both)
--output-dir PATH                   Output directory (default: output_report)
--no-interactive                    Disable interactive prompts (e.g., manual PDF download)
--no-download-pdfs                  Skip PDF download, use abstract-only extraction
--max-pdf-downloads N               Maximum number of PDFs to download
--agentic                           Enable agentic document extraction (OCR + VLM)
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

**Agentic Extraction (advanced PDF analysis)**
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G --agentic
```

**Non-interactive Mode (for automation)**
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G --no-interactive
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
  --output-dir analysis_results \
  --agentic
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
    pdf_path="papers",
    download_pdfs=True,
    interactive=False,  # Disable manual PDF prompts
)

# Access results
decision = result["assessment"]["decision"]      # "PS3", "BS3", or "none"
strength = result["assessment"]["strength"]      # "very_strong", "strong", "moderate", "supporting"
confidence = result["assessment"]["confidence"]  # "high", "medium", "low"
narrative = result["assessment"]["narrative"]    # Detailed explanation

print(f"Decision: {decision} ({strength})")
print(f"Narrative: {narrative}")

# Process experiments
for exp in result["experiments"]:
    print(f"PMID {exp['pmid']}: {exp['assay_type']} - {exp['evaluation']}")
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
    results[key] = analyze_variant(**variant, interactive=False)

# Save results
with open("batch_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
```

---

## Agentic Extraction

The `--agentic` flag enables advanced document extraction using:

- **OCR**: EasyOCR (recommended for macOS) or PaddleOCR for text extraction
- **Layout Detection**: Identifies text, tables, charts, and figures
- **LayoutReader**: LayoutLMv3-based reading order detection
- **VLM Tools**: Vision-language models (GPT-4o) for analyzing tables and charts
- **LangChain Agents**: Orchestrates extraction across document pages

### When to Use Agentic Extraction

- Papers with complex tables containing experimental data
- Documents with charts/figures showing functional results
- When standard PDF text extraction misses important information
- Multi-column layouts that confuse standard extractors

### Configuration

```env
# In .env file
USE_AGENTIC_EXTRACTION=true        # Enable by default
AGENTIC_VLM_MODEL=gpt-4o           # Better vision model (recommended)
USE_PADDLEOCR=false                # Use EasyOCR on macOS
```

Or via command line:
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G --agentic
```

### Performance Notes

- Agentic extraction is slower than standard extraction
- Requires more API calls (vision model for each table/chart)
- Produces more accurate results for complex documents
- First run downloads OCR and layout models (~2GB)

---

## Project Structure

```
LLM_PS3_BS3_pipeline/
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
│   ├── filtering.py         # LLM-based filtering and PDF extraction
│   ├── agentic_extraction.py # Agentic document extraction (OCR + VLM)
│   ├── assessment.py        # PS3/BS3 decision logic
│   ├── html_report.py       # HTML and PDF report generation
│   ├── reporting.py         # Console reporting
│   └── not_used/            # Unused/archived code for reference
│
├── output_report/           # Generated reports (HTML/PDF)
├── func_papers_pdf/         # Downloaded literature PDFs
│
└── notebooks/               # Jupyter notebooks (optional)
    ├── 01_preprocess_clingen.ipynb
    ├── 02_abstract_class_bench.ipynb
    └── 03_full_text_class_bench.ipynb
```

### Module Descriptions

| Module | Purpose |
|--------|---------|
| **main.py** | CLI entry point with argument parsing |
| **src/config.py** | Environment variable configuration and validation |
| **src/llm.py** | Multi-provider LLM initialization (OpenAI, Anthropic, Gemini) |
| **src/utils.py** | Data classes: VariantInfo, CandidatePaper, FunctionalPaper, FunctionalExperiment, IntegratedAssessment |
| **src/vep.py** | Ensembl VEP REST API integration for variant annotation |
| **src/litvar2.py** | LitVar2 and PubMed literature retrieval + PDF download workflow |
| **src/filtering.py** | LLM-based paper filtering and PDF experiment extraction |
| **src/agentic_extraction.py** | Advanced agentic extraction with OCR, layout detection, and VLM tools |
| **src/assessment.py** | Evidence integration and PS3/BS3 decision logic |
| **src/html_report.py** | HTML and PDF report generation |
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

### Evidence Strength Levels

The pipeline assigns strength levels based on evidence quality:
- **very_strong**: Multiple independent, well-controlled studies with consistent results
- **strong**: Well-established functional studies with clear results
- **moderate**: Good evidence but with some limitations
- **supporting**: Some functional evidence but insufficient for higher strength

---

## Output Formats

### 1. HTML Report
```
output_report/chr_pos_ref_alt_version.html
```

Example output: `2_162279995_C_G_GRCh38.html`

- Professional, interactive web page
- Contains all analysis results
- Mobile-responsive design
- Viewable in any web browser
- Easy to share and archive

### 2. PDF Report
```
output_report/chr_pos_ref_alt_version.pdf
```

Example output: `2_162279995_C_G_GRCh38.pdf`

- Print-ready PDF document
- Same content as HTML report
- Suitable for archiving and sharing
- Requires WeasyPrint (see Installation)

### 3. Both HTML and PDF (Default)
```bash
python main.py --chrom 2 --pos 162279995 --ref C --alt G --output-format both
```
Generates both HTML and PDF reports in the output directory.

### 4. Dictionary Format
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
    "confidence": "high",
    "narrative": "...",
    "key_pmids": ["12345678", "23456789"]
  },
  "downloaded_pdfs": {...}
}
```
- Printed to stdout as JSON
- Can be saved to file: `python main.py ... --output-format dict > results.json`
- Suitable for programmatic processing

### 5. Literature PDF Downloads (Automatic)
```
func_papers_pdf/
├── 12345678.pdf
├── 23456789.pdf
└── ...
```
- Automatically downloaded from PubMed Central or publisher links
- Used for full-text experiment extraction
- Location customizable via `--pdf-path` argument

### Manual PDF Download

If PDFs cannot be automatically downloaded, the pipeline will prompt you with instructions:

```
================================================================================
MANUAL PDF DOWNLOAD REQUIRED
================================================================================

The following 3 paper(s) could not be automatically downloaded:

  1. PMID 12345678
     PubMed: https://pubmed.ncbi.nlm.nih.gov/12345678/
  ...

INSTRUCTIONS:
--------------------------------------------------------------------------------
1. Visit PubMed links above and find the full-text PDF
2. Download each PDF and save it to: /path/to/func_papers_pdf
3. Name each file using its PMID: 12345678.pdf
--------------------------------------------------------------------------------

Options:
  [c] Continue - I've added PDFs, re-check and continue with analysis
  [s] Skip - Continue with abstract-only extraction for missing PDFs
  [q] Quit - Exit the program
```

Use `--no-interactive` to skip this prompt and use abstract-only extraction automatically.

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
    download_pdfs: bool = True,
    max_pdf_downloads: Optional[int] = None,
    interactive: bool = True,
) -> Dict[str, Any]:
```

**Parameters:**
- `chrom` (str): Chromosome (e.g., "1", "2", "X")
- `pos` (int): Genomic position (1-based)
- `ref` (str): Reference allele
- `alt` (str): Alternate allele
- `assembly` (str): Genome assembly version (default: "GRCh38")
- `pdf_path` (str, optional): Directory to save functional paper PDFs
- `download_pdfs` (bool): Whether to download PDFs (default: True)
- `max_pdf_downloads` (int, optional): Maximum PDFs to download
- `interactive` (bool): Enable interactive prompts (default: True)

**Returns:**
- Dictionary with keys: `variant_info`, `candidate_papers`, `functional_papers`, `experiments`, `assessment`, `downloaded_pdfs`

**Example:**
```python
result = analyze_variant("2", 162279995, "C", "G", interactive=False)
print(result["assessment"]["decision"])
```

---

## Examples

See `examples.py` for complete Python examples:

1. Simple variant analysis
2. Using different LLM model (Claude)
3. Batch analysis of multiple variants
4. Custom HTML report generation
5. Extracting specific data from results
6. Analyzing with different genome assemblies
7. Agentic extraction mode
8. Non-interactive batch processing

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

5. PDF Download (optional)
   ↓
   Download full-text PDFs for functional papers

6. Experiment Extraction
   ↓
   Extract detailed experiment information using LLM
   (Standard or Agentic extraction mode)

7. Evidence Integration
   ↓
   Consolidate experiments and make PS3/BS3 call with strength

8. Report Generation
   ↓
   Generate HTML/PDF report and/or dictionary output
```

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
- `LLM_PROVIDER` - Provider choice (openai, anthropic, gemini; default: openai)
- `LLM_MODEL` - Model override (default depends on provider)
- `USE_AGENTIC_EXTRACTION` - Enable agentic extraction by default (default: false)
- `AGENTIC_VLM_MODEL` - Vision model for agentic extraction (default: gpt-4o-mini)
- `USE_PADDLEOCR` - Force PaddleOCR on macOS (default: false, uses EasyOCR)

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
- **Solution:** Normal for some variants. The pipeline will still attempt VEP annotation.

### HTML Generation Fails

**Error:** Failed to generate HTML report
- **Solution:** Use `--output-format dict` instead, or check browser can open HTML files

### PDF Generation Fails

**Error:** WeasyPrint not available
- **Solution:** Install system dependencies and WeasyPrint (see Installation section)

### Timeout Issues

**Error:** API timeout or no response
- **Solution:** Try again later, check internet connection, verify APIs are accessible

### Agentic Extraction Issues

**Error:** OCR engine not available
- **Solution:** Install EasyOCR (`pip install easyocr`) or PaddleOCR (`pip install paddleocr paddlepaddle`)

**Error:** PaddleOCR segfault on macOS
- **Solution:** Use EasyOCR instead (default on macOS) or set `USE_PADDLEOCR=false`

**Error:** poppler not found (pdf2image)
- **Solution:** Install poppler system package:
  - macOS: `brew install poppler`
  - Ubuntu: `sudo apt-get install poppler-utils`

**Error:** LayoutReader model download fails
- **Solution:** Ensure internet connection; models are downloaded on first use (~2GB)

---

## Performance Tips

1. **First run is slower** due to API calls, PDF downloads, and model downloads (agentic mode)
2. **Model selection affects speed/accuracy**: `gpt-4o-mini` is faster, `gpt-4o` is more accurate
3. **Batch processing**: Use `interactive=False` for automated pipelines
4. **Cache results**: Save HTML/PDF reports for documentation
5. **Agentic mode**: Only use when needed for complex documents (slower but more thorough)

---

## Citation

If you use this pipeline in research, please cite:

```
AcmGENTIC: PS3/BS3 Functional Evidence Analysis Pipeline
Available at: https://github.com/AliSaadatV/AcmGENTIC
```

