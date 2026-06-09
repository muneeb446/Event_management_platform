# AI Chatbot Setup — 2 Minutes

The EventHub AI Assistant uses Claude (claude-sonnet) to answer user questions.

## Step 1: Get your Anthropic API Key
1. Go to https://console.anthropic.com/
2. Sign up / log in
3. Go to **API Keys** → click **Create Key**
4. Copy the key (starts with `sk-ant-...`)

## Step 2: Set the environment variable

### Windows
```
set ANTHROPIC_API_KEY=sk-ant-your-key-here
python app.py
```

### Mac / Linux
```
export ANTHROPIC_API_KEY=sk-ant-your-key-here
python app.py
```

### Or hardcode in app.py (dev only)
In the `chat_api()` function, replace:
```python
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
```
With:
```python
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

## What the chatbot can do
- Guide users on how to register for events
- Help download tickets and certificates
- Explain password reset steps
- Answer navigation questions
- Describe platform features

The chatbot appears as a 🤖 floating button on all user pages.
