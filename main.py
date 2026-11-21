import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:12b")
MAX_TRANSCRIPT_CHARS = 10000
SUMMARIZE_PATTERN = re.compile(
    r"\b(summari[sz]\w*|tl;?dr|recap)\b",
    re.IGNORECASE,
)


def ollama_base_url() -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    if "://" not in host:
        host = "http://" + host
    return host


def _windows_curl() -> str | None:
    found = shutil.which("curl.exe")
    if found:
        return found
    candidate = "/mnt/c/Windows/System32/curl.exe"
    if os.path.exists(candidate):
        return candidate
    return None


def _post_via_windows_curl(url: str, payload: bytes) -> dict:
    """Reach Ollama on the Windows host when this process runs inside WSL."""
    curl = _windows_curl()
    if curl is None:
        raise RuntimeError(
            f"Cannot reach Ollama at {url}. Start `ollama serve`, or set OLLAMA_HOST."
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as handle:
        handle.write(payload)
        payload_path = handle.name

    try:
        curl_path = payload_path
        if payload_path.startswith("/"):
            converted = subprocess.run(
                ["wslpath", "-w", payload_path],
                check=True,
                capture_output=True,
                text=True,
            )
            curl_path = converted.stdout.strip()

        result = subprocess.run(
            [
                curl,
                "-sS",
                "-m",
                "600",
                url,
                "-H",
                "Content-Type: application/json",
                "-d",
                f"@{curl_path}",
            ],
            check=False,
            capture_output=True,
        )
    finally:
        os.remove(payload_path)

    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(detail or "Ollama request failed")

    return json.loads(result.stdout.decode("utf-8"))


def ollama_generate(prompt: str) -> str:
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"num_predict": 400},
        }
    ).encode()
    url = ollama_base_url() + "/api/generate"
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"Ollama HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError):
        data = _post_via_windows_curl(url, payload)

    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))

    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama returned an empty summary")
    return text


class SummaryBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


bot = SummaryBot()


def clamp_limit(limit: int) -> int:
    return max(1, min(limit, 100))


def summary_prompt(transcript: str) -> str:
    return (
        "Summarize this Discord chat log into concise bullet points covering "
        "key topics, decisions, and notable moments:\n\n" + transcript
    )


async def channel_transcript(channel, limit: int, skip_message_id: int | None = None) -> str:
    messages = [msg async for msg in channel.history(limit=limit)]
    messages.reverse()
    lines = [
        f"{msg.author.display_name}: {msg.content}"
        for msg in messages
        if msg.id != skip_message_id and msg.content and not msg.author.bot
    ]
    transcript = "\n".join(lines)
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[-MAX_TRANSCRIPT_CHARS:]
    return transcript


async def summarize_transcript(transcript: str) -> str:
    return await asyncio.to_thread(ollama_generate, summary_prompt(transcript))


def mention_asks_for_summary(content: str) -> int | None:
    text = re.sub(r"<@!?\d+>", " ", content)
    if not SUMMARIZE_PATTERN.search(text):
        return None
    count = re.search(r"\b(\d{1,3})\b", text)
    if count is None:
        return 30
    return clamp_limit(int(count.group(1)))


@bot.tree.command(name="summarize", description="Summarize recent messages in this channel")
@app_commands.describe(limit="Number of recent messages to summarize (max 100)")
async def summarize(interaction: discord.Interaction, limit: int = 30):
    await interaction.response.defer(thinking=True)
    transcript = await channel_transcript(interaction.channel, clamp_limit(limit))
    if not transcript:
        await interaction.followup.send("No text messages found to summarize.")
        return

    try:
        summary = await summarize_transcript(transcript)
    except Exception as error:
        await interaction.followup.send(f"Summarize failed: {error}"[:1950])
        return

    await interaction.followup.send(summary[:1950])


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or bot.user not in message.mentions:
        return
    limit = mention_asks_for_summary(message.content)
    if limit is None:
        return

    async with message.channel.typing():
        transcript = await channel_transcript(
            message.channel,
            limit,
            skip_message_id=message.id,
        )
        if not transcript:
            await message.reply("No text messages found to summarize.")
            return
        try:
            summary = await summarize_transcript(transcript)
        except Exception as error:
            await message.reply(f"Summarize failed: {error}"[:1950])
            return

    await message.reply(summary[:1950])


bot.run(os.getenv("DISCORD_TOKEN"))
