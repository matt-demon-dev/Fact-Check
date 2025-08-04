import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, time
import pytz
import discord
from discord.ext import commands, tasks

# Load .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Config file to store channel, time, timezone
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {"channel_id": 0, "hour": 12, "minute": 0, "timezone": "UTC"}

# Load config
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = DEFAULT_CONFIG
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# Fetch fact (API first, Google fallback)
def fetch_fact() -> str:
    try:
        api_res = requests.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=10)
        api_res.raise_for_status()
        return api_res.json().get("text", "Couldn't fetch a fact today.")
    except Exception as e:
        print(f"⚠️ API failed: {e}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get("https://www.google.com/search?q=random+fact", headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        fact_div = soup.find("div", class_="BNeawe s3v9rd AP7Wnd")
        if fact_div:
            return fact_div.get_text(strip=True)
    except Exception as e:
        print(f"⚠️ Google scraping failed: {e}")

    return "Couldn't fetch a fact today."

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if config["channel_id"]:
        schedule_task()
        print(f"📢 Daily facts will post in channel ID {config['channel_id']} at {config['hour']:02}:{config['minute']:02} {config['timezone']}")
    else:
        print("⚠️ No channel set. Use !setchannel and !settime to configure.")

def schedule_task():
    # Cancel previous loop if running
    if post_fact_daily.is_running():
        post_fact_daily.cancel()
    # Convert configured time to UTC
    tz = pytz.timezone(config["timezone"])
    local_time = tz.localize(datetime.now().replace(hour=config["hour"], minute=config["minute"], second=0, microsecond=0))
    utc_time = local_time.astimezone(pytz.UTC).time()
    post_fact_daily.change_interval(time=utc_time)
    post_fact_daily.start()

@tasks.loop(time=time(12, 0))  # Default placeholder; will be updated
async def post_fact_daily():
    channel = bot.get_channel(config["channel_id"])
    if channel is None:
        try:
            channel = await bot.fetch_channel(config["channel_id"])
        except:
            print("❌ Could not find channel.")
            return
    fact = fetch_fact()
    try:
        await channel.send(f"📌 **Fact of the Day:**\n{fact}")
        print(f"✅ Fact posted at {datetime.utcnow()} UTC")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")

# Commands
@bot.command()
async def fact(ctx):
    await ctx.send(f"📌 **Random Fact:**\n{fetch_fact()}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    config["channel_id"] = ctx.channel.id
    save_config()
    await ctx.send("✅ This channel is now set for daily facts!")
    if not post_fact_daily.is_running():
        schedule_task()

@bot.command()
@commands.has_permissions(administrator=True)
async def settime(ctx, hhmm: str, tz: str):
    try:
        hour, minute = map(int, hhmm.split(":"))
        pytz.timezone(tz)  # Validate timezone
        config["hour"], config["minute"], config["timezone"] = hour, minute, tz
        save_config()
        schedule_task()
        await ctx.send(f"✅ Daily post time updated to {hour:02}:{minute:02} {tz}")
    except Exception as e:
        await ctx.send(f"❌ Invalid format or timezone. Example: `!settime 15:30 America/New_York`\nError: {e}")

@bot.command()
async def status(ctx):
    tz = config["timezone"]
    await ctx.send(f"📢 Channel: <#{config['channel_id']}>\n🕒 Time: {config['hour']:02}:{config['minute']:02} {tz}")

bot.run(TOKEN)
