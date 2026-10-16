import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up intents (only what we need)
intents = discord.Intents.default()
intents.message_content = True  # For reading commands
intents.voice_states = True     # For voice functionality

bot = commands.Bot(command_prefix='.', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print('------')

# Load music cog
@bot.event
async def setup_hook():
    await bot.load_extension('music')

# Run bot with token from environment variable
bot.run(os.getenv('DISCORD_TOKEN'))