# 🧭 College Compass (Streamlit)

College Compass recommends top universities based on:
- Intended major
- Region/area you want to study in
- Degree level + preferences (scholarships, research focus, etc.)

It uses **both**:
- **Perplexity API** for web-grounded research + citations
- **OpenAI API** for reasoned ranking and personalized summaries in a strict JSON schema

---

## ✅ Project Structure

```
college-compass/
  app.py
  services/
    perplexity_client.py
    openai_client.py
    ranker.py
  utils/
    schemas.py
    cache.py
    formatters.py
  requirements.txt
  README.md
  .gitignore
  .env
```

---

## 🚀 Setup

### 1) Create and activate a virtual environment (recommended)

**macOS/Linux**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Add your API keys

This project includes a `.env` file template. Put your keys there, or set environment variables.

**Option A: Export environment variables**

macOS/Linux:
```bash
export OPENAI_API_KEY="your_openai_key"
export PERPLEXITY_API_KEY="your_perplexity_key"
```

Windows (PowerShell):
```powershell
setx OPENAI_API_KEY "your_openai_key"
setx PERPLEXITY_API_KEY "your_perplexity_key"
```
Restart terminal after using `setx`.

**Option B: Use `.env`**
If you use `.env`, load it in your shell (example for macOS/Linux):
```bash
set -a
source .env
set +a
```

Optional:
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `LOG_LEVEL` (default: `INFO`)

---

## ▶️ Run the app

```bash
streamlit run app.py
```

---

## 🔑 How to get API keys and set environment variables

### OpenAI
1. Create an API key in your OpenAI account dashboard.
2. Set it as `OPENAI_API_KEY` in your environment (or in `.env`).

### Perplexity
1. Create an API key in your Perplexity API dashboard.
2. Set it as `PERPLEXITY_API_KEY` in your environment (or in `.env`).

Never commit real keys to Git.
