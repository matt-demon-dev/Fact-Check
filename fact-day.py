import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, time
import pytz
import discord
from discord.ext import commands, tasks
from discord import app_commands

# Load environment
dotenv_path = load_dotenv()
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
bot = commands.Bot(command_prefix="/", intents=intents)

# Sync slash commands on ready
def setup_hook():
    bot.loop.create_task(bot.tree.sync())
bot.setup_hook = setup_hook

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
def post_fact_daily():
    channel = bot.get_channel(config["channel_id"])
    if channel is None:
        return
    fact = fetch_fact()
    bot.loop.create_task(channel.send(f"📌 **Fact of the Day:**\n{fact}"))
    print(f"✅ Posted at {datetime.utcnow()} UTC")

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

# Slash commands
@bot.tree.command(name="fact", description="Get a random fact instantly")
async def slash_fact(interaction: discord.Interaction):
    await interaction.response.send_message(f"📌 **Random Fact:**\n{fetch_fact()}")

@bot.tree.command(name="setchannel", description="Set this channel for daily facts")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setchannel(interaction: discord.Interaction):
    config["channel_id"] = interaction.channel_id
    save_config()
    schedule_task()
    await interaction.response.send_message(
        f"✅ This channel is set for daily facts.", ephemeral=True
    )

@slash_setchannel.error
async def slash_setchannel_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need Administrator permissions.", ephemeral=True
        )

@bot.tree.command(name="settime", description="Set the daily post time and timezone. Format HH:MM Timezone")
@app_commands.checks.has_permissions(administrator=True)
async def slash_settime(
    interaction: discord.Interaction,
    hhmm: str,
    timezone: str
):
    try:
        hour, minute = map(int, hhmm.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Hour or minute out of range.")
        pytz.timezone(timezone)
        config.update({"hour": hour, "minute": minute, "timezone": timezone})
        save_config()
        schedule_task()
        await interaction.response.send_message(
            f"✅ Time updated to {hour:02}:{minute:02} {timezone}", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            "❌ Invalid format or timezone.\nExample: `/settime 15:30 America/New_York`\n"
            f"Error: {e}", ephemeral=True
        )

@bot.tree.command(name="status", description="Show current channel and post time")
async def slash_status(interaction: discord.Interaction):
    ch = f"<#{config['channel_id']}>" if config['channel_id'] else "Not set"
    await interaction.response.send_message(
        f"📢 Channel: {ch}\n🕒 Time: {config['hour']:02}:{config['minute']:02} {config['timezone']}",
        ephemeral=True
    )

@bot.tree.command(name="timezones", description="Show example valid timezones")
async def slash_timezones(interaction: discord.Interaction):
    examples = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]
    await interaction.response.send_message(
        "✅ Example Timezones:\n" + "\n".join(examples) +
        "\nFull list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        ephemeral=True
    )

bot.run(TOKEN)
