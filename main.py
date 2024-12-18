import discord
from discord.ext import commands
from discord import FFmpegPCMAudio, Embed
from discord.ui import Button, View
import yt_dlp as youtube_dl
from apikeys import *
import asyncio

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents = discord.Intents.all()

client = commands.Bot(command_prefix='!', intents=intents)

# YTDL Options for streaming YouTube, Spotify, SoundCloud audio
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
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

ffmpeg_options = {
    'options': '-vn'
}

# Initialize youtube_dl (yt-dlp)
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Create a dictionary to hold queues for each voice channel
song_queues = {}

# Keep track of the currently playing song
currently_playing = {}


# Event: Bot is ready
@client.event
async def on_ready():
    print("The bot is now initialized and ready to play music!")
    print("-" * 40)


# Command: Join the voice channel
@client.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        print(f"Bot connected to the voice channel: {channel.name}")
        await ctx.reply("🎤 Connected to the voice channel!")
    else:
        await ctx.reply("⚠️ You need to join a voice channel first!")


# Command: Play music from YouTube, Spotify, or SoundCloud
@client.command()
async def play(ctx, url: str):
    if not ctx.voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            print(f"Bot joined the channel: {channel.name}")
        else:
            await ctx.reply("⚠️ You need to join a voice channel first!")
            return

    voice_client = ctx.voice_client

    # Extract audio source from YouTube, Spotify, or SoundCloud using yt-dlp
    try:
        loop = client.loop
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'formats' in data:
            # Look for the best audio-only stream
            audio_url = None
            for format in data['formats']:
                if format.get('acodec') != 'none':
                    audio_url = format['url']
                    break

            if audio_url:
                # Check if there's already a queue for the channel
                if ctx.guild.id not in song_queues:
                    song_queues[ctx.guild.id] = []

                song_queues[ctx.guild.id].append((audio_url, data['title'], url))

                # If no song is currently playing, start the first one
                if not voice_client.is_playing():
                    await play_first_song(ctx, data, url)
                else:
                    # If song is added to the queue while another song is playing, only send a simple queue message
                    message = await ctx.send(f"🎶 **{data['title']}** has been added to the queue.")

                    # Delete the message after 20 seconds
                    await asyncio.sleep(20)
                    await message.delete()

            else:
                await ctx.reply("❌ Error: No valid audio stream found.")
        else:
            await ctx.reply("❌ Error: Unable to extract audio. Please check the URL.")
    except Exception as e:
        print(f"Error: {e}")
        await ctx.reply("❌ Error: Could not play the song. Please ensure the link is valid.")


# Function to play the first song in the queue
async def play_first_song(ctx, data, url):
    # Get the first song from the queue
    audio_url, title, _ = song_queues[ctx.guild.id].pop(0)
    voice_client = ctx.voice_client

    print(f"🎶 Now playing: {title} - {url}")

    voice_client.play(FFmpegPCMAudio(audio_url, **ffmpeg_options),
                      after=lambda e: client.loop.create_task(after_song_finish(ctx, e)))

    # Create embed for the message with video thumbnail and details
    embed = Embed(title=f"🎶 **{title}**",
                  description=f"**Now playing**\n\n"
                              f"👤 **Requested by**: {ctx.author.display_name}\n\n",
                  color=discord.Color.blurple())

    # Add video thumbnail and URL (only works for supported platforms)
    embed.set_thumbnail(url=data.get('thumbnail', 'https://example.com/default-thumbnail.jpg'))
    embed.add_field(name="🎧 Watch on Platform", value=f"[Click here]({url})", inline=False)

    # Create buttons for Skip, Pause, Resume, Stop
    skip_button = Button(label="Skip", style=discord.ButtonStyle.red, custom_id="skip_button")
    pause_button = Button(label="Pause", style=discord.ButtonStyle.blurple, custom_id="pause_button")
    resume_button = Button(label="Resume", style=discord.ButtonStyle.green, custom_id="resume_button")
    stop_button = Button(label="Stop", style=discord.ButtonStyle.danger, custom_id="stop_button")

    # Create a view with the buttons
    view = View()
    view.add_item(skip_button)
    view.add_item(pause_button)
    view.add_item(resume_button)
    view.add_item(stop_button)

    # Save the currently playing song
    currently_playing[ctx.guild.id] = {"url": url, "title": title, "view": view, "message": None}

    # Send the embed message with the buttons
    message = await ctx.reply(embed=embed, view=view)

    # Store the message in the dictionary to be deleted later
    currently_playing[ctx.guild.id]["message"] = message


# Function to play the next song in the queue
async def play_next_song(ctx):
    if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
        # Get the next song from the queue
        audio_url, title, url = song_queues[ctx.guild.id].pop(0)

        voice_client = ctx.voice_client
        print(f"🎶 Now playing: {title} - {url}")

        voice_client.play(FFmpegPCMAudio(audio_url, **ffmpeg_options),
                          after=lambda e: client.loop.create_task(after_song_finish(ctx, e)))

        # Create embed for the message with video thumbnail and details
        embed = Embed(title=f"🎶 **{title}**",
                      description=f"**Now playing**\n\n"
                                  f"👤 **Requested by**: {ctx.author.display_name}\n\n",
                      color=discord.Color.blurple())

        embed.set_thumbnail(
            url='https://example.com/default-thumbnail.jpg')  # Replace with actual thumbnail if available
        embed.add_field(name="🎧 Watch on Platform", value=f"[Click here]({url})", inline=False)

        skip_button = Button(label="Skip", style=discord.ButtonStyle.red, custom_id="skip_button")
        pause_button = Button(label="Pause", style=discord.ButtonStyle.blurple, custom_id="pause_button")
        resume_button = Button(label="Resume", style=discord.ButtonStyle.green, custom_id="resume_button")
        stop_button = Button(label="Stop", style=discord.ButtonStyle.danger, custom_id="stop_button")

        view = View()
        view.add_item(skip_button)
        view.add_item(pause_button)
        view.add_item(resume_button)
        view.add_item(stop_button)

        currently_playing[ctx.guild.id] = {"url": url, "title": title, "view": view, "message": None}

        message = await ctx.reply(embed=embed, view=view)

        # Store the message in the dictionary to be deleted after the song ends
        currently_playing[ctx.guild.id]["message"] = message

        print(f"Bot is playing: {title} - {url}")


# After the song finishes, play the next one in the queue
async def after_song_finish(ctx, error):
    if error:
        print(f"Error playing song: {error}")

    # Delete the "Now Playing" message after the song finishes
    if ctx.guild.id in currently_playing and currently_playing[ctx.guild.id]["message"]:
        await currently_playing[ctx.guild.id]["message"].delete()

    # Play the next song if there are any left in the queue
    await play_next_song(ctx)


# Handling the button clicks:
@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        guild_id = interaction.guild.id

        # Only allow interaction if the song matches the currently playing song
        if guild_id in currently_playing:
            current_song = currently_playing[guild_id]

            if custom_id == "skip_button":
                if interaction.user.voice and interaction.user.voice.channel == interaction.guild.voice_client.channel:
                    interaction.guild.voice_client.stop()
                    skip_message = await interaction.response.send_message("⏭️ Skipped the current song.")
                    # Delete the skip message after 20 seconds
                    await asyncio.sleep(20)
                    await skip_message.delete()
                else:
                    await interaction.response.send_message("⚠️ You're not in the correct voice channel.")

            elif custom_id == "pause_button":
                if interaction.guild.voice_client.is_playing():
                    interaction.guild.voice_client.pause()
                    pause_message = await interaction.response.send_message("⏸️ Paused the music.")
                    # Delete the pause message after 20 seconds
                    await asyncio.sleep(20)
                    await pause_message.delete()
                else:
                    await interaction.response.send_message("⚠️ No audio is currently playing to pause.")

            elif custom_id == "resume_button":
                if interaction.guild.voice_client.is_paused():
                    interaction.guild.voice_client.resume()
                    resume_message = await interaction.response.send_message("▶️ Resumed the music.")
                    # Delete the resume message after 20 seconds
                    await asyncio.sleep(20)
                    await resume_message.delete()
                else:
                    await interaction.response.send_message("⚠️ No audio is currently paused to resume.")

            elif custom_id == "stop_button":
                # Stop the music, clear the queue, and disconnect
                interaction.guild.voice_client.stop()
                song_queues[interaction.guild.id] = []  # Clear the queue
                stop_message = await interaction.response.send_message("⏹️ Stopped the music and cleared the queue.")
                # Delete the stop message after 20 seconds
                await asyncio.sleep(20)
                await stop_message.delete()

        else:
            await interaction.response.send_message(
                "❌ You cannot control music because no song is currently playing or the song has changed.")


# Run the bot with your token
client.run(BotToken)
