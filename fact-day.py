import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, time
import pytz
import discord
from discord.ext import tasks

# Load environment
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Config file
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {"channel_id": 0, "hour": 12, "minute": 0, "timezone": "UTC"}

# Load or initialize config
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

# Utility to save config
def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# Fetch fact (API first, fallback to scraping)
def fetch_fact() -> str:
    try:
        res = requests.get(
            "https://uselessfacts.jsph.pl/random.json?language=en", timeout=10
        )
        res.raise_for_status()
        return res.json().get("text", "Couldn't fetch a fact today.")
    except Exception as e:
        print(f"⚠️ API error: {e}")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(
            "https://www.google.com/search?q=random+fact",
            headers=headers,
            timeout=10
        )
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        div = soup.find("div", class_="BNeawe s3v9rd AP7Wnd")
        if div:
            return div.get_text(strip=True)
    except Exception as e:
        print(f"⚠️ Scrape error: {e}")
    return "Couldn't fetch a fact today."

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if config["channel_id"]:
        schedule_task()
        print(
            f"📢 Posting daily facts to channel {config['channel_id']} at "
            f"{config['hour']:02}:{config['minute']:02} {config['timezone']}"
        )
    else:
        print("⚠️ No channel set. Use /setchannel and /settime to configure.")

# Schedule or reschedule the daily task
def schedule_task():
    if post_fact_daily.is_running():
        post_fact_daily.stop()
    tz = pytz.timezone(config["timezone"])
    now = datetime.now(tz)
    run_dt = now.replace(
        hour=config["hour"], minute=config["minute"], second=0, microsecond=0
    )
    utc_time = run_dt.astimezone(pytz.UTC).time()
    post_fact_daily.change_interval(time=utc_time)
    post_fact_daily.start()

@tasks.loop(time=time(0, 0))  # placeholder, updated by schedule_task
async def post_fact_daily():
    channel = bot.get_channel(config["channel_id"])
    if channel is None:
        try:
            channel = await bot.fetch_channel(config["channel_id"])
        except Exception:
            print("❌ Channel fetch failed.")
            return
    fact = fetch_fact()
    try:
        await channel.send(f"📌 **Fact of the Day:**\n{fact}")
        print(f"✅ Posted at {datetime.utcnow()} UTC")
    except Exception as e:
        print(f"❌ Send error: {e}")

# Slash command: Get an instant fact\@bot.slash_command(name="fact", description="Get a random fact instantly")
async def fact(ctx: discord.ApplicationContext):
    await ctx.respond(f"📌 **Random Fact:**\n{fetch_fact()}")

# Slash command: Set the daily fact channel (Admin only)
@bot.slash_command(name="setchannel", description="Set current channel for daily facts")
async def setchannel(ctx: discord.ApplicationContext):
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("❌ You need Administrator permissions.", ephemeral=True)
        return
    config["channel_id"] = ctx.channel.id
    save_config()
    schedule_task()
    await ctx.respond(f"✅ This channel ({ctx.channel.mention}) is set for daily facts.")

# Slash command: Set time and timezone (Admin only)
@bot.slash_command(name="settime", description="Set post time and timezone. Format HH:MM Timezone")
async def settime(ctx: discord.ApplicationContext, hhmm: str, timezone: str):
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("❌ You need Administrator permissions.", ephemeral=True)
        return
    try:
        hour, minute = map(int, hhmm.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Hour or minute out of range.")
        pytz.timezone(timezone)
        config.update({"hour": hour, "minute": minute, "timezone": timezone})
        save_config()
        schedule_task()
        await ctx.respond(f"✅ Time updated to {hour:02}:{minute:02} {timezone}")
    except Exception as e:
        await ctx.respond(
            "❌ Invalid format or timezone.\nExample: `/settime 15:30 America/New_York`\n"
            f"Error: {e}", ephemeral=True
        )

# Slash command: Show current settings
@bot.slash_command(name="status", description="Show current channel and post time")
async def status(ctx: discord.ApplicationContext):
    ch = f"<#{config['channel_id']}>" if config['channel_id'] else "Not set"
    await ctx.respond(
        f"📢 Channel: {ch}\n🕒 Time: {config['hour']:02}:{config['minute']:02} {config['timezone']}",
        ephemeral=True
    )

# Slash command: List example timezones
@bot.slash_command(name="timezones", description="Show example valid timezones")
async def timezones(ctx: discord.ApplicationContext):
    examples = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]
    await ctx.respond(
        "✅ Example Timezones:\n" + "\n".join(examples) +
        "\nFull list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        ephemeral=True
    )

bot.run(TOKEN)
