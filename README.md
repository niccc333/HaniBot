# Hani

A small Discord bot that:

- Welcomes each new member once when they join.
- Replies with a link when someone runs `/hanilink`.
- Wishes happy birthday daily with a random message + GIF (from `birthdays.csv`).

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
   | `BIRTHDAY_CHANNEL_ID`| **Channel for birthday wishes. See Birthdays below for where to put it.**|
   | `BIRTHDAY_CSV_PATH`  | Path to birthday CSV. Default: `birthdays.csv`.                         |
   | `BIRTHDAY_CHECK_HOUR`| Hour (0-23) to post daily. Default: `9`.                                |
   | `BIRTHDAY_TIMEZONE`  | IANA timezone e.g. `Europe/Berlin`. Blank = machine local time.         |

   To get a channel ID: enable **Settings > Advanced > Developer Mode**, then
   right-click the channel and choose **Copy Channel ID**.
   To get a user ID: same Developer Mode, right-click the user > **Copy User ID**.

## Birthdays

1. **Set the channel:** in `.env`, paste the channel ID here:
   ```ini
   BIRTHDAY_CHANNEL_ID=1341435970934804601
   ```
   (Copy via right-click channel > Copy Channel ID. See `.env.example`.)
2. **Add birthdays** to `birthdays.csv` (header required, private — gitignored):
   ```powershell
   Copy-Item birthdays.example.csv birthdays.csv
   ```
   ```csv
   name,birthday,user_id
   Hani,04-23,123456789012345678
   ```
   - `name`: display name in the message.
   - `birthday`: `MM-DD` (e.g. `04-23`), repeats yearly.
   - `user_id`: Discord numeric ID so Hani pings `<@id>`. Blank = plain name, no ping.
   - Edit + save anytime — the file is re-read on every daily check, no restart needed.
   - Bad rows are skipped with a warning in the logs, never crash.
3. **GIFs/messages:** edit `BIRTHDAY_GIFS` / `BIRTHDAY_MESSAGES` at the top of `bot.py` to customize the random pool.

3. Install dependencies and run:

   ```powershell
   python -m pip install -r requirements.txt
   python bot.py
   ```

   You should see `Logged in as Hani`.

## Usage

- Join the server with a second account to see the welcome message.
- Run `/hanilink` in any channel to get the link.
- Birthdays: Hani posts daily at `BIRTHDAY_CHECK_HOUR` in `BIRTHDAY_CHANNEL_ID`.
  Run `/birthdays_today` to preview today's matches + message without double-posting.
  Tip for testing: add a row with today's `MM-DD` + your `user_id`, restart the bot,
  and check the birthday channel.
