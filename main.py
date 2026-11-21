import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from google import genai

load_dotenv()
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class SummaryBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = SummaryBot()

@bot.tree.command(name="summarize", description="Summarize recent messages in this channel")
@app_commands.describe(limit="Number of recent messages to summarize (max 100)")
async def summarize(interaction: discord.Interaction, limit: int = 30):
    await interaction.response.defer(thinking=True)
    limit = max(1, min(limit, 100))

    messages = [msg async for msg in interaction.channel.history(limit=limit)]
    messages.reverse()

    transcript = "\n".join(
        f"{m.author.display_name}: {m.content}"
        for m in messages
        if m.content and not m.author.bot
    )

    if not transcript:
        await interaction.followup.send("No text messages found to summarize.")
        return

    prompt = (
        "Summarize this Discord chat log into concise bullet points covering "
        "key topics, decisions, and notable moments:\n\n" + transcript
    )

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    await interaction.followup.send(response.text[:1950])

bot.run(os.getenv("DISCORD_TOKEN"))

