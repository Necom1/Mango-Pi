import re
import typing

import yaml
import discord
import wavelink
from discord.ext import commands
from Components.MangoPi import MangoPi


def setup(bot: MangoPi):
    """
    Essential function for Cog loading that calls the update method of MusicPlayer Cog (to fetch data from Mongo)
    before adding it to the bot.
    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to append the Cog
    """
    bot.add_cog(Music(bot))
    print("Load Cog:\tMusicPlayer")


def teardown(bot: MangoPi):
    """
    Method for Cog unload, this function will print to Console that MusicPlayer Cog got unload.
    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to unload the Cog
    """
    bot.remove_cog("Music")
    print("Unload Cog:\tMusic")


def convert_seconds(sec: int):
    """
    Function that attempts to convert the passed in seconds into minutes and seconds

    Parameters
    ----------
    sec: int
        seconds for conversion

    Returns
    -------
    int, int
        first integer as minute and the second as seconds
    """
    mini = int(sec / 60)
    sec %= 60

    return mini, int(sec)


async def get_player(ctx: commands.Context, channel_check: bool = True):
    """
    Static async function that fetches the appropriate AudioPlayer base on passed in context

    Parameters
    ----------
    ctx: commands.Context
        pass in context for processing
    channel_check: bool
        whether to check for the channel correctness

    Returns
    -------
    vc
        AudioPlayer base on the passed in context

    discord.Message
        error has occurred
    """
    try:
        channel = ctx.author.voice.channel
    except AttributeError:
        return await ctx.reply("Please join a voice channel before using this command")

    if not ctx.voice_client:
        ap = AudioPlayer(ctx)
        ap.channel_id = channel.id
        vc: AudioPlayer = await channel.connect(cls=ap)
    else:
        vc: AudioPlayer = ctx.voice_client

    if channel.id != vc.channel_id and channel_check:
        return await ctx.reply("Please be in the same voice channel as the bot to request songs")

    return vc


class AudioPlayer(wavelink.Player):
    """
    AudioPlayer class inherits from wavelink.Player class

    Attributes
    ----------
    limit: int
        the queue limit for the player
    queue: list
        current songs in the player in queue order
    volume: int
        current player volume
    repeat: bool
        whether to repeat the song currently playing
    channel_id: int
        the ID of the voice channel the bot is currently connected to
    """
    def __init__(self, ctx: commands.Context, limit: int = 15):
        """
        Constructor of AudioPlayer

        Parameters
        ----------
        ctx: commands.Context
            pass in context for initialization
        limit: int
            set the limit of the queue of the player, default of 15
        """
        super().__init__()
        self.limit = limit
        self.queue = []
        self.volume = 100
        self.repeat = False
        self.channel_id = ctx.author.voice.channel.id

    def change_volume(self, change: int = 100):
        """
        Method to change the curreny player volume

        Parameters
        ----------
        change: int
            the new set volume for the player
        """
        if 0 <= change <= 1000:
            self.set_volume(change)
            self.volume = change


class Music(commands.Cog):
    """
    Class inherited from commands.Cog that contains music player commands

    Attributes
    ----------
    bot: MangoPi
        bot reference for the Cog
    """

    def __init__(self, bot: MangoPi):
        """
        constructor for the Cog class

        Parameters
        ----------
        bot: MangoPi
            pass in bot reference
        """
        self.bot = bot
        self.bot.loop.create_task(self.start_nodes())

    async def cog_check(self, ctx: commands.Context):
        """
        Async method that does the command check before running

        Parameters
        ----------
        ctx: commands.Context
            pass in context to check

        Returns
        -------
        bool
            whether or not to run commands within this Cog
        """
        if self.bot.ignore_check(ctx):
            return False

        return not isinstance(ctx.channel, discord.DMChannel)

    async def start_nodes(self):
        """
        Async function that reads data from application.yml and attempt to connect to the local lavalink server
        """
        await self.bot.wait_until_ready()

        with open('application.yml', 'r') as yml:
            opn = yaml.safe_load(yml)
            link = opn['server']['address']
            port = opn['server']['port']
            await wavelink.NodePool.create_node(bot=self.bot,
                                                host=link,
                                                port=port,
                                                password=opn['lavalink']['server']['password'],
                                                identifier='MAIN',
                                                region=discord.VoiceRegion.eu_west)

    @commands.group(aliases=['mp'])
    async def music_player(self, ctx: commands.Context):
        """Music player command group for Youtube and Soundcloud"""
        if not ctx.invoked_subcommand:
            return

    @music_player.command(aliases=['connect'])
    async def join(self, ctx: commands.Context):
        """Joins the voice chat of the caller"""
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.reply("Please join a voice channel before using this command")

        player = await get_player(ctx, False)
        if isinstance(player, discord.Message):
            return

        if player.is_connected():
            await player.move_to(channel.id)
            player.channel_id = channel.id
        else:
            await player.connect(channel.id)

        await ctx.message.add_reaction(emoji='➡')

    @music_player.command(aliases=['disconnect'])
    async def leave(self, ctx: commands.Context):
        """Leave the current voice chat"""
        player = await get_player(ctx)

        if isinstance(player, discord.Message):
            return

        if player.is_connected():
            await ctx.invoke(self.stop)
            await player.disconnect()
            await ctx.message.add_reaction(emoji='👋')

    @music_player.command(aliases=['+'])
    async def play(self, ctx: commands.Context, *, query: typing.Union[wavelink.YouTubeTrack,
                                                                       wavelink.SoundCloudTrack]):
        """Attempt to play audio from user given URL or to resume playing if no link is given"""
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.reply("Please join a voice channel before using this command")

        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        if not player.is_connected():
            await player.connect(60, False)

        if channel.id != player.channel_id:
            return await ctx.reply("Please be in the same voice channel as the bot to request songs")

        if len(player.queue) > player.limit:
            return await ctx.reply(f"Reached the max limit of song queue of {player.limit}")

        player.queue.append(query)

        if not player.is_playing():
            await player.play(query)

        await ctx.reply(f"Added to queue: {query.uri}")

    @music_player.command(aliases=['-'])
    async def remove(self, ctx: commands.Context, position: int):
        """Remove a song from the queue"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        if 0 < position < len(player.queue):
            r = player.queue.pop(position)
            await ctx.reply(f"Removed position {position} from queue: {r.uri}")
        else:
            await ctx.reply("Invalid position, please check the queue")

    @music_player.command()
    async def pause(self, ctx: commands.Context):
        """Stop the player if it is stopped"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        if not player.is_paused():
            await player.pause()
            await ctx.message.add_reaction(emoji='⏸')
        else:
            await player.resume()
            await ctx.message.add_reaction(emoji='▶')

    @music_player.command()
    async def stop(self, ctx: commands.Context):
        """Stop the music player and purge the current queue"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        player.queue.clear()
        if player.is_connected():
            await player.stop()
            await ctx.message.add_reaction(emoji='⏹')

    @music_player.command()
    async def skip(self, ctx: commands.Context):
        """Skip the song currently playing if any"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        if not player.is_connected():
            return await ctx.reply("Currently not in any VC")

        if len(player.queue) < 1:
            return await ctx.reply("Nothing in queue")

        player.queue.pop(0)

        if len(player.queue) > 0:
            await player.play(player.queue[0])
        else:
            await player.stop()
        await ctx.message.add_reaction(emoji='👍')

    @music_player.command()
    async def volume(self, ctx: commands.Context, volume: int = None):
        """Change volume of the music player from 0 to 1000"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        if not volume:
            return await ctx.reply(f"Current volume: {player.volume}")

        if volume > 1000:
            return await ctx.reply("Value is too big")

        if volume < 0:
            volume = 0

        await player.set_volume(volume)
        await ctx.message.add_reaction(emoji='👌')

    @music_player.command()
    async def jump(self, ctx: commands.Context, time: str = "0"):
        """Jump to a specific point in the current song. Format: hours**:**minutes**:**seconds"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        temp = list(re.findall(r'(\d+)', time))
        if 1 > len(temp) > 2:
            return await ctx.reply("Unknown time jump format, try to keep it in `(hours):(minutes):(seconds)`")

        total = 0
        cal = (1, 60, 3600)
        for i, v in enumerate(reversed(temp)):
            total += int(v) * cal[i]
        total_ms = total * 1000

        if len(player.queue) < 1:
            return await ctx.send("No tracks currently playing")

        if total > player.queue[0].length:
            return await ctx.reply("Requested jump time exceeds the track duration.")

        emote = '⏩'
        if player.position > total:
            emote = '⏪'

        await player.seek(total_ms)
        await ctx.message.add_reaction(emoji=emote)

    @music_player.command()
    async def queue(self, ctx: commands.Context):
        """Show the queue of the music player"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        data = player.queue

        if len(data) < 1:
            return await ctx.reply("Empty Queue")

        embed = discord.Embed(
            colour=0xf8a5c2,
            title="Music Player Queue"
        )

        end = f"🔊{player.volume}"

        if player.is_connected():
            end += " | "
            end += "Paused" if player.is_paused() else "Vibin'"

        m1, s1 = convert_seconds(player.position)
        m2, s2 = convert_seconds(data[0].length)

        embed.set_footer(text=end)

        embed.add_field(inline=False, name=f"Currently Playing |\t{m1}:{s1} / {m2}:{s2}",
                        value=f"[{data[0].title}]({data[0].uri})" if data[0].uri else f"{data[0].title}")

        if len(data) > 1:
            temp = ""
            for i in range(1, len(data)):
                temp += f"{i}. "
                temp += f"[{data[i].title}]({data[i].uri})\n" if data[i].uri else f"{data[i].title}\n"
            embed.add_field(inline=False, name="Upcoming...", value=temp)
        await ctx.send(embed=embed)

    @music_player.command()
    async def now(self, ctx: commands.Context):
        """Show information on the song currently playing"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        data = player.source
        if not data:
            return await ctx.reply("Nothing is playing ATM")

        m1, s1 = convert_seconds(player.position)
        m2, s2 = convert_seconds(data.length)

        embed = discord.Embed(
            colour=0xf8a5c2,
            title="Now Playing",
            description=f"{m1}:{s1} / {m2}:{s2}"
        )

        end = f"🔊{player.volume}"

        if player.is_connected():
            end += " | "
            end += "Paused" if player.is_paused() else "Vibin'"

        embed.set_author(url=data.uri, name=data.title)
        if data.thumb:
            embed.set_image(url=data.thumbnail)
        await ctx.reply(embed=embed)

    @music_player.command()
    async def repeat(self, ctx: commands.Context):
        """Set music player to repeat the current song"""
        player = await get_player(ctx)
        if isinstance(player, discord.Message):
            return

        if player.repeat:
            player.repeat = False
            await ctx.message.add_reaction(emoji='➡')
        else:
            player.repeat = True
            await ctx.message.add_reaction(emoji='🔁')

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: AudioPlayer, track: wavelink.Track, reason: str):
        """
        Async event method to be called automatically when a song finished playing. Will attempt to play next in queue
        """
        if reason == 'REPLACED':
            return

        if not player.repeat:
            try:
                player.queue.pop(0)
                if len(player.queue) < 1:
                    return
            except IndexError:
                return

        await player.play(player.queue[0])
