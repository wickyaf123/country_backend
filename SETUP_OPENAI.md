# OpenAI API Key Setup

## Required for GPT-4 Consolidation

The new hybrid strategy uses GPT-4 to consolidate research reports from Perplexity into unified JSON.

### Add to .env file

Add this line to your `/backend/.env` file:

```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
```

### Get Your API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-`)
4. Add it to your `.env` file

### Verify It's Working

The system will automatically load the key from `.env`. To verify:

```bash
cd backend
python -c "from config import settings; print('OpenAI key configured:', bool(settings.openai_api_key))"
```

Should output: `OpenAI key configured: True`

### Cost Estimates

GPT-4 Turbo Preview pricing:
- Input: $0.01 per 1K tokens
- Output: $0.03 per 1K tokens

For our use case (consolidating 3 reports per keyword):
- ~$0.01 per keyword
- ~$0.50 for 50 keywords

### Fallback Behavior

If OpenAI API key is not configured:
- System falls back to using only Degree 1 (reasoning-pro) results
- You'll see warning in logs: "OpenAI API key not configured, falling back to D1 only"
- Still works but gets fewer connections

### Model Selection

Default model: `gpt-4-turbo-preview` (configured in config.py)

You can change in `.env`:
```bash
OPENAI_MODEL=gpt-4-turbo-preview  # or gpt-4, gpt-4o, etc.
```







