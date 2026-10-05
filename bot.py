import csv
import datetime
import logging
import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()


def _clean_env(name: str, default: str = "") -> str:
    """Get env var stripped of whitespace. Empty string if unset."""
    return (os.getenv(name, default) or "").strip()


TOKEN = _clean_env("DISCORD_TOKEN")
WELCOME_CHANNEL_ID = _clean_env("WELCOME_CHANNEL_ID")
HANI_LINK_URL = _clean_env("HANI_LINK_URL", "https://example.com") or "https://example.com"
GUILD_ID = _clean_env("GUILD_ID")
# Default Discord "Wave" sticker (Wumpus waves hello, animated Lottie)
WELCOME_STICKER_ID = _clean_env("WELCOME_STICKER_ID", "749054660769218631") or "749054660769218631"

# --- Birthdays ---
# Birthdays post ONLY to this channel ID — no fallback to any other channel.
# Discord with Developer Mode ON > right-click your birthday channel > Copy Channel ID,
# then set BIRTHDAY_CHANNEL_ID in your .env file (local) or Railway Variables (hosted).
BIRTHDAY_CHANNEL_ID = _clean_env("BIRTHDAY_CHANNEL_ID")
BIRTHDAY_CSV_PATH = _clean_env("BIRTHDAY_CSV_PATH", "birthdays.csv") or "birthdays.csv"
BIRTHDAY_CHECK_HOUR_RAW = _clean_env("BIRTHDAY_CHECK_HOUR", "9") or "9"
BIRTHDAY_TIMEZONE = _clean_env("BIRTHDAY_TIMEZONE")

try:
    BIRTHDAY_CHECK_HOUR = int(BIRTHDAY_CHECK_HOUR_RAW)
    if not 0 <= BIRTHDAY_CHECK_HOUR <= 23:
        raise ValueError
except ValueError:
    BIRTHDAY_CHECK_HOUR = 9

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("hani")


def start_health_server() -> None:
    """Start a tiny HTTP server so Railway (and uptime pingers) see the bot as live.

    Railway injects PORT and expects web services to listen on it. Discord bots
    don't serve HTTP, so without this the service can look unhealthy / restart.
    This stdlib-only server answers GET / and /health with 200 OK in a daemon
    thread — no extra dependencies. Harmless for Worker services too.
    Disable Railway healthchecks OR keep them pointed at / — both work.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = b"OK: Hani is alive"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, fmt, *args):  # keep Railway logs clean
            return

    port_raw = _clean_env("PORT", "8080") or "8080"
    try:
        port = int(port_raw)
    except ValueError:
        log.warning("PORT %r invalid, defaulting to 8080", port_raw)
        port = 8080

    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
    except OSError:
        log.exception("Health server could not bind to port %s (bot still runs)", port)
        return

    thread = threading.Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    log.info("Health server listening on 0.0.0.0:%s", port)


intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Curated starter pool — add/remove your favourite Tenor/Giphy URLs here.
# A random one is picked per birthday wish. Discord auto-embeds these links.
BIRTHDAY_GIFS = [
    "https://tenor.com/view/happy-birthday-happybirthday-birthday-wishes-wishes-balloons-gif-1993892125166777462",
    "https://tenor.com/view/birthday-happy-birthday-dancing-skeleton-happy-gif-26290215",
    "https://tenor.com/view/birthday-cake-gif-1496343852284377582",
    "https://tenor.com/view/transparent-happy-birthday-bday-candles-birthday-cake-gif-144719990881744979",
    "https://tenor.com/view/its-my-birthday-glitter-party-gif-14536658235220580453",
    "https://tenor.com/view/happy-birthday-birthday-confetti-celebrate-celebrating-gif-2225398293568770601",
    "https://tenor.com/view/happy-birthday-foreverfriend-gif-1563934671476079812",
    "https://tenor.com/view/80th-birthday-happy-birthday-happy-birthday-to-you-hbd-birthday-gif-16286244",
]

BIRTHDAY_MESSAGES = [
    "🎂 Happy Birthday {mention}! Hope your day is wonderful! 🥳",
    "🎉 Happy Birthday {mention}! Wishing you cake, laughs, and good vibes! 🎁",
    "🥳 Hey {mention}, happy birthday! Make a wish and celebrate big! 🎂",
    "🎈 Happy Birthday {mention}! Hope Hani made your day a little brighter! ✨",
    "🍰 Happy Birthday {mention}! Another trip around the sun — enjoy it! ☀️",
]

# (date_iso, dedupe_key) already wished, so reconnects/restarts don't double-post.
_already_wished: set[tuple[str, str]] = set()


def _get_birthday_tz() -> datetime.tzinfo | None:
    if BIRTHDAY_TIMEZONE:
        try:
            return ZoneInfo(BIRTHDAY_TIMEZONE)
        except ZoneInfoNotFoundError:
            log.warning("BIRTHDAY_TIMEZONE %r not found, using local time.", BIRTHDAY_TIMEZONE)
    try:
        return datetime.datetime.now().astimezone().tzinfo
    except Exception:
        return None


def _get_check_time() -> datetime.time:
    tz = _get_birthday_tz()
    if tz is None:
        return datetime.time(hour=BIRTHDAY_CHECK_HOUR, minute=0)
    return datetime.time(hour=BIRTHDAY_CHECK_HOUR, minute=0, tzinfo=tz)


def _resolve_csv_path() -> Path:
    p = Path(BIRTHDAY_CSV_PATH)
    if not p.is_absolute():
        p = Path(__file__).parent / p
    return p


def load_birthdays(path: str | Path | None = None) -> list[dict]:
    """Parse birthdays CSV. Expected header: name,birthday,user_id.

    birthday is MM-DD (e.g. 04-23). user_id is the Discord numeric ID for
    pinging (right-click user > Copy User ID); may be blank (no ping).
    Invalid rows are skipped with a warning, never crash.
    Returns list of {name, month, day, user_id}.
    """
    csv_path = Path(path) if path else _resolve_csv_path()
    entries: list[dict] = []
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                log.warning("Birthday CSV %s is empty.", csv_path)
                return []
            # Normalize headers: case/whitespace-insensitive.
            norm = { (h or "").strip().lower(): h for h in reader.fieldnames }
            if "name" not in norm or "birthday" not in norm:
                log.warning(
                    "Birthday CSV %s missing required header (need name,birthday,user_id). Got: %r",
                    csv_path, reader.fieldnames,
                )
                return []
            name_key, bday_key = norm["name"], norm["birthday"]
            uid_key = norm.get("user_id")
            for lineno, row in enumerate(reader, start=2):
                name = (row.get(name_key) or "").strip()
                bday_raw = (row.get(bday_key) or "").strip()
                uid_raw = (row.get(uid_key) or "").strip() if uid_key else ""
                if not name and not bday_raw and not uid_raw:
                    continue  # blank line
                if not bday_raw:
                    log.warning("Birthday CSV %s line %d: missing birthday, skipped.", csv_path, lineno)
                    continue
                try:
                    parsed = datetime.datetime.strptime(bday_raw, "%m-%d")
                except ValueError:
                    log.warning(
                        "Birthday CSV %s line %d: bad birthday %r (want MM-DD), skipped.",
                        csv_path, lineno, bday_raw,
                    )
                    continue
                user_id: int | None = None
                if uid_raw:
                    try:
                        user_id = int(uid_raw)
                    except ValueError:
                        log.warning(
                            "Birthday CSV %s line %d: bad user_id %r, will post without ping.",
                            csv_path, lineno, uid_raw,
                        )
                if not name:
                    name = f"<@{user_id}>" if user_id else "friend"
                entries.append({"name": name, "month": parsed.month, "day": parsed.day, "user_id": user_id})
    except FileNotFoundError:
        log.warning("Birthday CSV not found: %s (no wishes will be sent).", csv_path)
    return entries


def todays_birthdays(entries: list[dict], today: datetime.date) -> list[dict]:
    return [e for e in entries if e["month"] == today.month and e["day"] == today.day]


def build_birthday_message(person: dict) -> str:
    mention = f"<@{person['user_id']}>" if person.get("user_id") else person["name"]
    template = random.choice(BIRTHDAY_MESSAGES)
    gif = random.choice(BIRTHDAY_GIFS)
    try:
        text = template.format(mention=mention, name=person["name"])
    except (KeyError, IndexError):
        text = f"🎂 Happy Birthday {mention}! 🥳"
    return f"{text}\n{gif}"


async def get_birthday_channel() -> discord.abc.Messageable | None:
    """Resolve ONLY the configured BIRTHDAY_CHANNEL_ID. Never falls back.

    Returns None (and skips posting) when the ID is missing, invalid, or the
    bot can't see the channel. Birthday wishes are never sent anywhere else.
    """
    if not BIRTHDAY_CHANNEL_ID:
        log.warning(
            "BIRTHDAY_CHANNEL_ID is not set; skipping birthday post. "
            "Set it to the birthday channel ID in .env locally / Railway Variables when hosted."
        )
        return None
    try:
        channel_id = int(BIRTHDAY_CHANNEL_ID)
    except ValueError:
        log.error("BIRTHDAY_CHANNEL_ID is not a valid integer: %r", BIRTHDAY_CHANNEL_ID)
        return None
    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            log.exception("Could not fetch birthday channel %s", channel_id)
            return None
    # Guard: only post to text-capable channels (text, announcement, thread, DM).
    # Voice/category/forum channels have no .send — skip instead of crashing.
    if not hasattr(channel, "send"):
        log.error(
            "BIRTHDAY_CHANNEL_ID %s is %s, which cannot receive messages. Use a text channel ID.",
            channel_id,
            type(channel).__name__,
        )
        return None
    return channel  # type: ignore[return-value]


async def check_and_send_birthdays(today: datetime.date | None = None, send: bool = True) -> list[dict]:
    """Load CSV, find today's matches, optionally post them (dedupe per day)."""
    tz = _get_birthday_tz()
    today = today or datetime.datetime.now(tz).date() if tz else datetime.date.today()
    today_iso = today.isoformat()
    # Drop dedupe keys from other days so the set stays small.
    for key in [k for k in _already_wished if k[0] != today_iso]:
        _already_wished.discard(key)

    entries = load_birthdays()
    matches = todays_birthdays(entries, today)
    if not matches:
        log.info("No birthdays on %s (%d entries checked).", today_iso, len(entries))
        return []

    fresh = [p for p in matches if (today_iso, str(p.get("user_id") or p["name"])) not in _already_wished]
    if not fresh:
        log.info("Birthdays for %s already wished, skipping.", today_iso)
        return matches

    if not send:
        return matches

    channel = await get_birthday_channel()
    if channel is None:
        return matches

    for person in fresh:
        try:
            await channel.send(build_birthday_message(person))  # type: ignore[attr-defined]
            _already_wished.add((today_iso, str(person.get("user_id") or person["name"])))
            log.info("Wished happy birthday to %s.", person["name"])
        except discord.Forbidden:
            log.error("Missing permission to send birthday in channel %s", getattr(channel, "id", "?"))
        except discord.HTTPException:
            log.exception("Failed to send birthday wish for %s", person["name"])
    return matches


@tasks.loop(time=_get_check_time())
async def birthday_loop():
    try:
        await check_and_send_birthdays()
    except Exception:
        log.exception("Birthday loop failed")


@birthday_loop.before_loop
async def _before_birthday_loop():
    await client.wait_until_ready()


@client.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", client.user, client.user.id)
    if BIRTHDAY_CHANNEL_ID:
        log.info("Birthday channel ID: %s (birthdays post ONLY there)", BIRTHDAY_CHANNEL_ID)
    else:
        log.warning("BIRTHDAY_CHANNEL_ID not set — birthdays will be detected but NOT posted.")
    if getattr(client, "_commands_synced", False):
        if not birthday_loop.is_running():
            try:
                birthday_loop.start()
            except Exception:
                log.exception("Failed to (re)start birthday loop")
        return
    try:
        if GUILD_ID:
            try:
                guild = discord.Object(id=int(GUILD_ID))
            except ValueError:
                log.error("GUILD_ID is not a valid integer: %r — falling back to global sync", GUILD_ID)
                guild = None
            if guild is not None:
                tree.copy_global_to(guild=guild)
                synced = await tree.sync(guild=guild)
                log.info("Synced %d guild commands to %s (instant)", len(synced), GUILD_ID)
            else:
                synced = await tree.sync()
                log.info("Synced %d global commands", len(synced))
        else:
            # Guild sync is instant; global sync can take up to 1 hour to appear.
            for guild in client.guilds:
                tree.copy_global_to(guild=guild)
                synced = await tree.sync(guild=guild)
                log.info(
                    "Synced %d guild commands to %s (instant)",
                    len(synced),
                    guild.id,
                )
            synced = await tree.sync()
            log.info("Synced %d global commands", len(synced))
        client._commands_synced = True
    except Exception:
        log.exception("Failed to sync slash commands")

    if not birthday_loop.is_running():
        try:
            birthday_loop.start()
            log.info("Birthday loop scheduled daily at %s", _get_check_time())
        except Exception:
            log.exception("Failed to start birthday loop")

    # Catch-up: if the bot started after today's check time, still wish today.
    try:
        await check_and_send_birthdays()
    except Exception:
        log.exception("Birthday catch-up check failed")


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
        # Sticker-only wave (no text). Falls back to 👋 if sticker send fails.
        try:
            sticker = await client.fetch_sticker(int(WELCOME_STICKER_ID))
            await channel.send(stickers=[sticker])
        except (ValueError, discord.NotFound, discord.Forbidden, discord.HTTPException):
            log.exception(
                "Could not send wave sticker %r, falling back to emoji",
                WELCOME_STICKER_ID,
            )
            await channel.send(f"👋 {member.mention}")
    except discord.Forbidden:
        log.error("Missing permission to send in channel %s", channel.id)


@tree.command(name="hanilink", description="Hani shares a link")
async def hanilink(interaction: discord.Interaction):
    await interaction.response.send_message(f"Here you go: {HANI_LINK_URL}")


@tree.command(name="birthdays_today", description="Preview whose birthday is today (no double-post)")
async def birthdays_today(interaction: discord.Interaction):
    entries = load_birthdays()
    tz = _get_birthday_tz()
    today = datetime.datetime.now(tz).date() if tz else datetime.date.today()
    matches = todays_birthdays(entries, today)
    if not matches:
        await interaction.response.send_message(
            f"No birthdays today ({today:%m-%d}). {len(entries)} entries checked.",
            ephemeral=True,
        )
        return
    lines = []
    for p in matches:
        mention = f"<@{p['user_id']}>" if p.get("user_id") else p["name"]
        lines.append(f"• {p['name']} ({p['month']:02d}-{p['day']:02d}) -> {mention}")
    preview = build_birthday_message(matches[0])
    await interaction.response.send_message(
        f"🎂 **{len(matches)} birthday(s) today:**\n" + "\n".join(lines) + f"\n\nPreview:\n{preview}",
        ephemeral=True,
    )


def main():
    if not TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is missing. Copy .env.example to .env and fill it in. "
            "On Railway, set it in Variables instead."
        )
    if not BIRTHDAY_CHANNEL_ID:
        log.warning(
            "BIRTHDAY_CHANNEL_ID is not set — birthdays will NOT be posted. "
            "Set it to your birthday channel's ID (Developer Mode > right-click channel > Copy Channel ID)."
        )
    elif not BIRTHDAY_CHANNEL_ID.isdigit():
        log.error("BIRTHDAY_CHANNEL_ID %r is not numeric — birthdays will NOT be posted.", BIRTHDAY_CHANNEL_ID)
    # Keep Railway / uptime pingers happy: listen on $PORT with a 200 OK health endpoint.
    start_health_server()
    # discord.py auto-reconnects; Railway restarts the process if it ever exits.
    client.run(TOKEN)


if __name__ == "__main__":
    main()
