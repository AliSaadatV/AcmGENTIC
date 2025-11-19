# Setup Instructions

## Project Layout

Your project is now organized as follows:

```
LLM_PS3_BS3/
├── main.py                 # ← Run this: python main.py
├── .env.example            # ← Copy to .env and fill with your credentials
├── .env                    # ← Your actual credentials (git-ignored)
├── .gitignore              # ← Prevents .env from being committed
├── README.md               # ← Full documentation
├── QUICKSTART.md           # ← Quick reference
├── SETUP.md                # ← This file
│
├── src/                    # ← All source code
│   ├── __init__.py
│   ├── config.py           # Loads environment variables from .env
│   ├── utils.py            # Data classes and utilities
│   ├── vep.py              # Variant annotation
│   ├── litvar2.py          # Literature search
│   ├── filtering.py        # LLM-based filtering
│   ├── assessment.py       # PS3/BS3 decision logic
│   ├── reporting.py        # Report generation
│   └── main.py             # Pipeline functions
│
└── notebooks/              # ← Jupyter notebooks (optional)
```

## Setup Steps

### Step 1: Install Dependencies

```bash
pip install requests langchain-openai langchain-core metapub python-dotenv
```

### Step 2: Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual credentials
nano .env  # or your preferred editor
```

Your `.env` file should look like:

```
OPENAI_API_KEY=sk-your-actual-key-here
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=your-ncbi-key-here
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0
```

### Step 3: Run the Pipeline

```bash
# From the project root directory
python main.py
```

This will analyze the example variant and generate a report.

## Key Changes from Previous Structure

1. **`main.py` moved to root** - Now you can run `python main.py` directly from project root
2. **`dotenv` integration** - Environment variables loaded from `.env` file
3. **`.env.example`** - Template showing what variables are needed
4. **`.gitignore`** - Prevents accidental commit of `.env` with API keys
5. **Better separation** - `src/main.py` now only contains pipeline functions (no main block)

## Security Notes

- **Do NOT commit `.env`** - It contains secret API keys
- `.gitignore` is configured to ignore `.env` files
- Use `.env.example` as a template for other developers
- Keep `OPENAI_API_KEY` and `NCBI_API_KEY` confidential

## How It Works

1. **Load Environment**: When you run `python main.py`:
   - `main.py` loads `.env` using `python-dotenv`
   - `src/config.py` reads environment variables
   - All API keys and settings are configured

2. **Run Pipeline**: The `analyze_variant()` function:
   - Queries Ensembl VEP for variant annotation
   - Searches LitVar2 for related literature
   - Filters papers using LLM
   - Extracts functional experiments
   - Makes PS3/BS3 decision

3. **Get Results**: Returns a dictionary with:
   - Variant information
   - Candidate papers
   - Functional papers
   - Extracted experiments
   - Assessment and decision

## Testing

To test if everything is set up correctly:

```python
# In Python REPL
from src.main import analyze_variant

# This should work if .env is configured correctly
result = analyze_variant("2", 162279995, "C", "G")
print(result["assessment"]["decision"])
```

## Troubleshooting

If you get `OPENAI_API_KEY not found` error:
- Check that `.env` file exists in project root
- Verify `OPENAI_API_KEY` is set in `.env`
- Run from project root directory

If imports fail:
- Make sure you're in the project root directory
- Verify `python-dotenv` is installed: `pip install python-dotenv`
- Check that `src/` folder has `__init__.py`

## Next Steps

1. Edit `main.py` to analyze your own variants
2. Customize LLM prompts in `src/filtering.py`
3. Adjust assessment logic in `src/assessment.py`
4. Create notebooks for exploratory analysis
5. Add unit tests in a `tests/` folder
