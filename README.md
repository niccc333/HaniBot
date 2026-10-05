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

Birthdays post **only** to `BIRTHDAY_CHANNEL_ID` — never to any other channel.
If the ID is missing/invalid, Hani logs a warning and skips posting.

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

## Hosting on Railway (always live)

Hani is Railway-ready: `railway.json` (start `python bot.py`, restart on failure),
`Procfile`, and a built-in health server that listens on Railway's `$PORT` and
answers `GET /` with `200 OK` so the service stays green.

1. Push this repo to GitHub (`.env` and `birthdays.csv` stay local — both are gitignored).
2. In [Railway](https://railway.app), **New Project > Deploy from GitHub**, pick this repo.
3. Open the service > **Variables** and add the same keys as `.env.example`:
   - `DISCORD_TOKEN` (required — from the Discord Developer Portal, never commit it)
   - `BIRTHDAY_CHANNEL_ID` (required — right-click birthday channel > Copy Channel ID;
     birthdays go **only** here)
   - `WELCOME_CHANNEL_ID`, `HANI_LINK_URL`, `GUILD_ID`, `BIRTHDAY_CHECK_HOUR`,
     `BIRTHDAY_TIMEZONE` as needed.
   - Do **not** set `PORT` yourself — Railway injects it.
4. Deploy. Logs should show `Logged in as Hani` + `Health server listening on 0.0.0.0:<PORT>`.
5. Keep it always live:
   - Railway restarts the bot automatically if it crashes (`restartPolicyType: ON_FAILURE`).
   - discord.py auto-reconnects on Discord disconnects.
   - Optional but recommended: add an UptimeRobot / BetterUptime / cron-job.org monitor
     pinging `https://<your-service>.up.railway.app/` every 5 minutes so you get alerted
     if it ever goes down. The endpoint always returns `OK: Hani is alive`.
   - `birthdays.csv` is gitignored, so Railway won't have it — upload your birthday list
     via Railway **Volumes** (mount at `/app`, put `birthdays.csv` there) or switch
     `BIRTHDAY_CSV_PATH` to a hosted source later. Without the file Hani logs
     `Birthday CSV not found` and posts nothing (never crashes).

> Security: never put your real `DISCORD_TOKEN` in code or `.env.example`.
> If a token ever leaks, reset it in the Developer Portal > Bot > Reset Token.
