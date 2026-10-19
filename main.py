import os
import discord
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='.', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print('------')

# Load music cog
@bot.event
async def setup_hook():
    await bot.load_extension('music')


bot.run(os.getenv('DISCORD_TOKEN'))