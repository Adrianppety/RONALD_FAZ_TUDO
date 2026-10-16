import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
import glob
import shutil
from collections import deque


def find_ffmpeg_executable():
    executable = shutil.which('ffmpeg')
    if executable:
        return executable

    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        package_pattern = os.path.join(
            local_app_data,
            'Microsoft',
            'WinGet',
            'Packages',
            'Gyan.FFmpeg_*',
            'ffmpeg-*',
            'bin',
            'ffmpeg.exe'
        )
        candidates = glob.glob(package_pattern)
        if candidates:
            return max(candidates, key=os.path.getmtime)

    return 'ffmpeg'


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.now_playing = {}
        self.voice_clients = {}

        # yt-dlp options
        self.ytdl_format_options = {
            'format': 'bestaudio/best',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0'
        }

        self.ffmpeg_options = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }
        self.ffmpeg_executable = find_ffmpeg_executable()

        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_format_options)

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]

    def get_voice_client(self, guild_id):
        return self.voice_clients.get(guild_id)

    def set_voice_client(self, guild_id, voice_client):
        self.voice_clients[guild_id] = voice_client

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)

        if len(queue) == 0:
            self.now_playing[guild_id] = None
            return

        # Get next song
        song_info = queue.popleft()
        self.now_playing[guild_id] = song_info

        # Play the song
        voice_client = self.get_voice_client(guild_id)
        if voice_client:
            source = discord.FFmpegPCMAudio(
                song_info['url'],
                executable=self.ffmpeg_executable,
                **self.ffmpeg_options
            )
            voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)))

            embed = discord.Embed(
                title="🎵 Tocando agora",
                description=f"[{song_info['title']}]({song_info['webpage_url']})",
                color=discord.Color.blue()
            )
            if song_info.get('thumbnail'):
                embed.set_thumbnail(url=song_info['thumbnail'])
            if song_info.get('duration'):
                mins, secs = divmod(song_info['duration'], 60)
                embed.add_field(name="Duração", value=f"{mins}:{secs:02d}", inline=True)

            await ctx.send(embed=embed)

    @commands.command(name='entrar', help='Entra no canal de voz')
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send("Você precisa estar em um canal de voz para usar este comando!")
            return

        channel = ctx.author.voice.channel

        if ctx.guild.id in self.voice_clients:
            await self.voice_clients[ctx.guild.id].move_to(channel)
        else:
            voice_client = await channel.connect()
            self.set_voice_client(ctx.guild.id, voice_client)

        await ctx.send(f"Entrei no canal: {channel.name}")

    @commands.command(name='sair', help='Sai do canal de voz')
    async def leave(self, ctx):
        if ctx.guild.id in self.voice_clients:
            voice_client = self.voice_clients[ctx.guild.id]
            await voice_client.disconnect()
            del self.voice_clients[ctx.guild.id]

            # Clear queue and now playing
            if ctx.guild.id in self.queues:
                self.queues[ctx.guild.id].clear()
            if ctx.guild.id in self.now_playing:
                self.now_playing[ctx.guild.id] = None

            await ctx.send("Saí do canal de voz!")
        else:
            await ctx.send("Eu não estou em nenhum canal de voz!")

    @commands.command(name='tocar', help='Toca uma música do YouTube (URL ou busca)')
    async def play(self, ctx, *, query):
        # Join voice channel if not already connected
        if ctx.guild.id not in self.voice_clients:
            if not ctx.author.voice:
                await ctx.send("Você precisa estar em um canal de voz para usar este comando!")
                return
            channel = ctx.author.voice.channel
            voice_client = await channel.connect()
            self.set_voice_client(ctx.guild.id, voice_client)

        # Show typing indicator
        async with ctx.typing():
            try:
                # Extract info from YouTube
                data = self.ytdl.extract_info(f"ytsearch:{query}" if not query.startswith('http') else query, download=False)

                if 'entries' in data:
                    # Take first result from search
                    data = data['entries'][0]

                song_info = {
                    'title': data.get('title', 'Título desconhecido'),
                    'url': data['url'],
                    'webpage_url': data.get('webpage_url', ''),
                    'thumbnail': data.get('thumbnail'),
                    'duration': data.get('duration')
                }

                # Add to queue
                queue = self.get_queue(ctx.guild.id)
                queue.append(song_info)

                # If nothing is playing, start playing
                voice_client = self.get_voice_client(ctx.guild.id)
                if not voice_client.is_playing():
                    await self.play_next(ctx)
                else:
                    embed = discord.Embed(
                        title="✅ Adicionado à fila",
                        description=f"[{song_info['title']}]({song_info['webpage_url']})",
                        color=discord.Color.green()
                    )
                    if song_info.get('thumbnail'):
                        embed.set_thumbnail(url=song_info['thumbnail'])
                    await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Erro ao processar a música: {str(e)}")

    @commands.command(name='pausar', help='Pausa a música atual')
    async def pause(self, ctx):
        voice_client = self.get_voice_client(ctx.guild.id)
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await ctx.send("⏸️ Música pausada!")
        else:
            await ctx.send("Nenhuma música está tocando no momento!")

    @commands.command(name='retomar', help='Retoma a música pausada')
    async def resume(self, ctx):
        voice_client = self.get_voice_client(ctx.guild.id)
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await ctx.send("▶️ Música retomada!")
        else:
            await ctx.send("Nenhuma música está pausada no momento!")

    @commands.command(name='pular', help='Pula a música atual')
    async def skip(self, ctx):
        voice_client = self.get_voice_client(ctx.guild.id)
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await ctx.send("⏭️ Música pulada!")
        else:
            await ctx.send("Nenhuma música está tocando no momento!")

    @commands.command(name='parar', help='Para a música e limpa a fila')
    async def stop(self, ctx):
        guild_id = ctx.guild.id
        voice_client = self.get_voice_client(guild_id)

        if voice_client:
            voice_client.stop()

        # Clear queue
        if guild_id in self.queues:
            self.queues[guild_id].clear()

        # Clear now playing
        if guild_id in self.now_playing:
            self.now_playing[guild_id] = None

        await ctx.send("⏹️ Música parada e fila limpa!")

    @commands.command(name='fila', help='Mostra a fila de músicas')
    async def queue(self, ctx):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        now_playing = self.now_playing.get(guild_id)

        if len(queue) == 0 and not now_playing:
            await ctx.send("📭 A fila está vazia!")
            return

        embed = discord.Embed(
            title="📋 Fila de Música",
            color=discord.Color.purple()
        )

        if now_playing:
            embed.add_field(
                name="🎵 Tocando agora",
                value=f"[{now_playing['title']}]({now_playing['webpage_url']})",
                inline=False
            )

        if len(queue) > 0:
            queue_text = ""
            for i, song in enumerate(list(queue)[:10], 1):  # Show first 10 songs
                queue_text += f"{i}. [{song['title']}]({song['webpage_url']})\n"

            if len(queue) > 10:
                queue_text += f"... e mais {len(queue) - 10} músicas"

            embed.add_field(
                name="📝 Próximas na fila",
                value=queue_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📝 Próximas na fila",
                value="Nenhuma música na fila",
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))