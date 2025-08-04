import os
import requests
from bs4 import BeautifulSoup
from datetime import time
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Channel persistence
CHANNEL_FILE = "channel.txt"
if os.path.exists(CHANNEL_FILE):
    with open(CHANNEL_FILE, "r") as f:
        CHANNEL_ID = int(f.read().strip())
else:
    CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ✅ Fetch fact from API (primary) or Google (fallback)
def fetch_fact() -> str:
    # Primary: API
    try:
        api_res = requests.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=10)
        api_res.raise_for_status()
        data = api_res.json()
        if "text" in data:
            return data["text"]
    except Exception as e:
        print(f"⚠️ API failed: {e}")

    # Fallback: Google scraping
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://www.google.com/search?q=random+fact"
        res = requests.get(url, headers=headers, timeout=10)
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
    if CHANNEL_ID:
        print(f"📢 Daily facts will post in channel ID: {CHANNEL_ID}")
        post_fact_daily.start()
    else:
        print("⚠️ No channel set. Use !setchannel (admin only) to set one.")

# ✅ Daily fact task at 12:00 UTC
@tasks.loop(time=time(hour=12, minute=0))
async def post_fact_daily():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except:
            print("❌ Could not find channel with given ID.")
            return

    fact = fetch_fact()
    try:
        await channel.send(f"📌 **Fact of the Day:**\n{fact}")
        print("✅ Fact posted.")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")

# ✅ Command: Fetch a fact instantly
@bot.command(name="fact")
async def fact_command(ctx):
    fact = fetch_fact()
    await ctx.send(f"📌 **Random Fact:**\n{fact}")

# ✅ Command: Set channel (admin/owner only)
@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    with open(CHANNEL_FILE, "w") as f:
        f.write(str(CHANNEL_ID))
    await ctx.send(f"✅ This channel has been set for daily facts!")
    print(f"✅ Channel updated to {CHANNEL_ID}")

@set_channel.error
async def set_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permissions to use this command.")

# ✅ Command: Show current daily fact channel
@bot.command(name="showchannel")
async def show_channel(ctx):
    if CHANNEL_ID:
        await ctx.send(f"📢 Current daily fact channel ID: `{CHANNEL_ID}`")
    else:
        await ctx.send("⚠️ No channel is set for daily facts.")

# Start the bot
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN is missing in .env")
    else:
        bot.run(TOKEN)
