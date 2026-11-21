# atgroksummarize

Discord slash command that summarizes recent channel messages with a local Ollama model.

## Setup

1. Install [Ollama](https://ollama.com) and pull the model:

```bash
ollama pull gemma4:12b
ollama serve
```

2. Create a Discord application with the Message Content intent enabled, invite the bot, and put the token in `.env`:

```
DISCORD_TOKEN=your-bot-token
```

Optional:

```
OLLAMA_MODEL=gemma4:12b
OLLAMA_HOST=http://127.0.0.1:11434
```

3. Install dependencies and run the bot:

```bash
python -m venv venv
source venv/bin/activate
pip install discord.py python-dotenv
python main.py
```

## Usage

`/summarize` reads up to 100 recent messages (default 30) and returns bullet points. Mentioning the bot with a similar request does the same thing, for example `@bot summarize`, `@bot summary`, `@bot tl;dr`, or `@bot recap 50`. Bot messages are skipped. The transcript is cut to the latest 10,000 characters so it fits the loaded model context.

If the bot runs in WSL and Ollama is listening only on Windows `127.0.0.1`, the request is sent with Windows `curl.exe`.
