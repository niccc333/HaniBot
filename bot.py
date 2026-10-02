import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WELCOME_CHANNEL_ID = os.getenv("WELCOME_CHANNEL_ID")
HANI_LINK_URL = os.getenv("HANI_LINK_URL", "https://example.com")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("hani")

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", client.user, client.user.id)
    if not getattr(client, "_commands_synced", False):
        await tree.sync()
        client._commands_synced = True
        log.info("Synced slash commands")


@client.event
async def on_member_join(member: discord.Member):
    channel = None

    if WELCOME_CHANNEL_ID:
        try:
            channel = member.guild.get_channel(int(WELCOME_CHANNEL_ID))
        except ValueError:
            log.error("WELCOME_CHANNEL_ID is not a valid integer: %r", WELCOME_CHANNEL_ID)

    if channel is None:
        channel = member.guild.system_channel

    if channel is None:
        log.warning("No welcome channel available for guild %s", member.guild.id)
        return

    try:
        await channel.send(
            f"Welcome {member.mention} to {member.guild.name}! I'm Hani \U0001F338"
        )
    except discord.Forbidden:
        log.error("Missing permission to send in channel %s", channel.id)


@tree.command(name="hanilink", description="Hani shares a link")
async def hanilink(interaction: discord.Interaction):
    await interaction.response.send_message(f"Here you go: {HANI_LINK_URL}")


def main():
    if not TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is missing. Copy .env.example to .env and fill it in."
        )
    client.run(TOKEN)


if __name__ == "__main__":
    main()
