# Hani

A small Discord bot that:

- Welcomes each new member once when they join.
- Replies with a link when someone runs `/hanilink`.

Built with Python and [discord.py](https://discordpy.readthedocs.io/).

## Setup

1. Create a bot at the [Discord Developer Portal](https://discord.com/developers/applications):
   - **Bot** > Reset Token > copy it.
   - Enable the **SERVER MEMBERS INTENT** under **Privileged Gateway Intents**.
   - **OAuth2 > URL Generator**: scopes `bot` + `applications.commands`, permissions `Send Messages`, `Embed Links`, `View Channels`. Open the generated URL to invite Hani.
2. Configure the environment:

   ```powershell
   Copy-Item .env.example .env
   ```

   Then edit `.env`:

   | Variable             | Description                                                              |
   | -------------------- | ------------------------------------------------------------------------ |
   | `DISCORD_TOKEN`      | Bot token from the developer portal.                                     |
   | `WELCOME_CHANNEL_ID` | Channel for welcome messages. Blank = server's system channel.          |
   | `HANI_LINK_URL`      | Link returned by `/hanilink`.                                            |

   To get a channel ID: enable **Settings > Advanced > Developer Mode**, then
   right-click the channel and choose **Copy Channel ID**.

3. Install dependencies and run:

   ```powershell
   python -m pip install -r requirements.txt
   python bot.py
   ```

   You should see `Logged in as Hani`.

## Usage

- Join the server with a second account to see the welcome message.
- Run `/hanilink` in any channel to get the link.
