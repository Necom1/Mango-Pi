import re
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


def milliseconds_to_seconds(milliseconds: int):
    """
    Function that attempts to convert the passed in milliseconds into minutes and seconds

    Parameters
    ----------
    milliseconds: int
        milliseconds for conversion

    Returns
    -------
    int, int
        first integer as minute and the second as seconds
    """
    sec = int(milliseconds / 1000)
    mini = int(sec / 60)
    sec %= 60

    return mini, sec


class Music(commands.Cog, wavelink.WavelinkMixin):
    """
    Class inherited from commands.Cog that contains music player commands

    Attributes
    ----------
    bot: MangoPi
        bot reference for the Cog
    music: wavelink.Client
        wavelink client to connect to lavalink
    queues: dict
        dictionary of list containing tracks for the music player with guild ID as key
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
        self.music = wavelink.Client(bot=self.bot)
        self.bot.loop.create_task(self.start_nodes())
        self.queues = {}

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
            await self.music.initiate_node(host=link,
                                           port=port,
                                           rest_uri=f'http://{link}:{port}',
                                           password=opn['lavalink']['server']['password'],
                                           identifier='MAIN',
                                           region='us_central')

    @commands.command(aliases=['connect'])
    async def join(self, ctx: commands.Context):
        """Joins the voice chat of the caller"""
        player = self.music.get_player(ctx.guild.id)

        if player.is_connected:
            return False

        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return ctx.reply("Please join a voice channel before using this command")

        await player.connect(channel.id)

        await ctx.message.add_reaction(emoji='➡')

    @commands.command(aliases=['disconnect'])
    async def leave(self, ctx: commands.Context):
        """Leave the current voice chat"""
        player = self.music.get_player(ctx.guild.id)
        if player.is_connected:
            await player.disconnect()
            await ctx.message.add_reaction(emoji='👋')

    @commands.command()
    async def play(self, ctx: commands.Context, *, query: str = ""):
        """Attempt to play audio from user given URL or to resume playing if no link is given"""
        if not query.startswith('http'):
            await ctx.reply("Please provide URL")

        player = self.music.get_player(ctx.guild.id)

        if len(query) < 1:
            if player.is_paused:
                await player.set_pause(False)
                await ctx.message.add_reaction(emoji='▶')
            return

        tracks = await self.music.get_tracks(query)

        if not tracks:
            return await ctx.send('Could not find any songs with that query.')

        if not player.is_connected:
            await ctx.invoke(self.join)

        try:
            if len(self.queues[ctx.guild.id]) > 9:
                return await ctx.reply("Reached the max limit of song queue")
            self.queues[ctx.guild.id].append(tracks[0])
        except KeyError:
            self.queues[ctx.guild.id] = [tracks[0]]

        if not player.is_playing:
            await player.play(self.queues[ctx.guild.id][0])

        if query.startswith('http'):
            await ctx.message.add_reaction(emoji='🎶')
        else:
            await ctx.reply(f'Added __{tracks[0].title}__ to the queue!\n{query}')

    @commands.command()
    async def pause(self, ctx: commands.Context):
        """Stop the player if it is stopped"""
        player = self.music.get_player(ctx.guild.id)
        if not player.is_paused:
            await player.set_pause(True)
            await ctx.message.add_reaction(emoji='⏸')

    @commands.command()
    async def stop(self, ctx: commands.Context):
        """Stop the music player and purge the current queue"""
        self.queues[ctx.guild.id] = []
        player = self.music.get_player(ctx.guild.id)
        if player.is_connected:
            await player.stop()
            await ctx.message.add_reaction(emoji='⏹')

    @commands.command()
    async def skip(self, ctx: commands.Context):
        """Skip the song currently playing if any"""
        player = self.music.get_player(ctx.guild.id)

        if not player.is_connected:
            return await ctx.reply("Currently not in any VC")

        try:
            data = self.queues[ctx.guild.id]
            if len(data) < 1:
                raise KeyError()
            data.pop(0)
        except KeyError:
            return await ctx.reply("Nothing to skip to")

        if len(data) > 0:
            await player.play(data[0])
        else:
            await player.stop()
        await ctx.message.add_reaction(emoji='👍')

    @commands.command()
    async def volume(self, ctx: commands.Context, volume: int = None):
        """Change volume of the music player from 0 to 1000"""
        player = self.music.get_player(ctx.guild.id)

        if not volume:
            return await ctx.reply(f"Current volume: {player.volume}")

        if 0 > volume > 1000:
            return await ctx.reply("Value is too big")

        await player.set_volume(volume)
        await ctx.message.add_reaction(emoji='👌')

    @commands.command()
    async def jump(self, ctx: commands.Context, time: str = "0"):
        """Jump to a specific point in the current song. Format: hours**:**minutes**:**seconds"""
        try:
            data = self.queues[ctx.guild.id][0]
        except (KeyError, IndexError):
            return await ctx.send("No tracks currently playing")

        temp = list(re.findall(r'(\d+)', time))
        if 1 > len(temp) > 2:
            return await ctx.reply("Unknown time jump format, try to keep it in `(hours):(minutes):(seconds)`")

        ite = 0
        total = 0
        cal = (1, 60, 3600)
        for i in reversed(temp):
            total += int(i) * cal[ite]
            ite += 1
        total *= 1000

        if total > data.length:
            return await ctx.reply("Requested jump time exceeds the track duration.")

        player = self.music.get_player(ctx.guild.id)
        emote = '⏩'
        if player.position > total:
            emote = '⏪'

        await player.seek(total)
        await ctx.message.add_reaction(emoji=emote)

    @commands.command()
    async def queue(self, ctx: commands.Context):
        """Show the queue of the music player"""
        try:
            data = self.queues[ctx.guild.id]
            if len(data) < 1:
                raise KeyError()
        except KeyError:
            return await ctx.reply("Empty Queue")

        player = self.music.get_player(ctx.guild.id)

        embed = discord.Embed(
            colour=0xf8a5c2,
            title="Music Player Queue"
        )

        end = f"🔊 {player.channel_id}"

        if player.is_connected:
            end += " | "
            end += "Paused" if player.is_paused else "Vibin'"

        m1, s1 = milliseconds_to_seconds(player.position)
        m2, s2 = milliseconds_to_seconds(data[0].length)

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

    @commands.command()
    async def now(self, ctx: commands.Context):
        """Show information on the song currently playing"""
        player = self.music.get_player(ctx.guild.id)

        try:
            data = self.queues[ctx.guild.id]
            if len(data) < 1:
                raise KeyError()
            if not player.is_playing:
                raise KeyError()
        except KeyError:
            return await ctx.reply("Nothing is playing ATM")

        m1, s1 = milliseconds_to_seconds(player.position)
        m2, s2 = milliseconds_to_seconds(data[0].length)

        embed = discord.Embed(
            colour=0xf8a5c2,
            title="Now Playing",
            description=f"{m1}:{s1} / {m2}:{s2}"
        )
        embed.set_author(url=data[0].uri, name=data[0].title)
        if data[0].thumb:
            embed.set_image(url=data[0].thumb)
        await ctx.reply(embed=embed)

    @wavelink.WavelinkMixin.listener(event='on_track_end')
    async def on_track_end(self, node: wavelink.node.Node, payload: wavelink.events.TrackEnd):
        """
        Async event method to be called automatically when a song finished playing. Will attempt to play next in queue

        Parameters
        ----------
        node: wavelink.node.Node
            wavelink node associated with the music player
        payload: wavelink.events.TrackEnd
            payload information
        """
        if payload.reason == 'REPLACED':
            return

        player = payload.player

        try:
            target = self.queues[player.guild_id]
            target.pop(0)
            if len(target) < 1:
                return
        except (KeyError, IndexError):
            return

        await player.play(target[0])
