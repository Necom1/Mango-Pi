import discord
from discord.ext import commands


class Ignore(commands.Cog):
    """
    Class inherited from commands.Cog that allows servers to set non-bot channel for normal commands.

    Attributes
    ----------
    bot : commands.Bot
        commands.Bot reference
    data : dict
        dictionary that stores all the channels to ignore for common commands
    db : MongoClient
        client for MongoDB "ignore_channel" collection
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor for Ignore class.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference for the Cog
        """
        self.bot = bot
        self.db = bot.mongo["ignore_channel"]
        self.data = {}

    def update(self, target: int = None):
        """
        Method that updates the data dictionary from MongoDB in it's entirety or a specific server.

        Parameters
        ----------
        target : int
            Update that specific server's ignore channel list if provided
        """
        if not target:
            self.data.clear()
            data = self.db.find({})
        else:
            data = self.db.find({"guild_id": target})
            try:
                self.data[target] = []
            except KeyError:
                self.data.update({target: []})
        for i in data:
            try:
                self.data[i['guild_id']].append(i['_id'])
            except KeyError:
                self.data.update({i['guild_id']: [i['_id']]})

    def find(self, guild: int, channel: int = None):
        """
        Method that will attempt to find the list of no-bot command channel or if that channel is one.

        Parameters
        ----------
        guild : int
            Server ID to search for
        channel : int
            Channel ID to search for if it applies

        Returns
        -------
        list
            List of no-bot command channels for that specified server
        bool
            Whether or not that specified channel is part of the ignore list
        """
        try:
            data = self.data[guild]
        except KeyError:
            return

        return data if not channel else (channel in data)

    def ignore_check(self, ctx: commands.Context, ignore_dm: bool = False):
        """
        A function that checks whether or not that channel allows command.

        Parameters
        ----------
        ctx : commands.Context
            pass in context for analysis
        ignore_dm : bool
            whether or not the command is being ignored in direct messages

        Returns
        -------
        bool
            Whether or not that channel is ignored
        """
        if not ctx.guild:
            return ignore_dm

        return self.find(ctx.guild.id, ctx.channel.id)

    @commands.command(aliases=['ic'])
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def ignore_channels(self, ctx: commands.Context):
        """List all the no-bot command channels of this server."""
        data = self.find(ctx.guild.id)
        display = "I take commands from all channels"

        if len(data) <= 0:
            return await ctx.send(display)
        else:
            display = ""
            for i in data:
                channel = ctx.guild.get_channel(i)
                if not channel:
                    self.db.delete_one({"guild_id": ctx.guild.id, "_id": i})
                else:
                    display += f"* {channel.mention}\n"

            embed = discord.Embed(
                title=f"I Ignore Common Commands From These Channels",
                colour=0x1289A7,
                description=display,
                timestamp=ctx.message.created_at
            ).set_thumbnail(url=ctx.guild.icon_url)

            if len(display) <= 0:
                await ctx.send("I take commands from all channels")
            else:
                await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def ignore(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Specified the channel for the bot to ignore or un-ignore."""
        channel = ctx.channel if not channel else channel
        data = self.find(ctx.guild.id, channel.id)

        if not data:
            self.db.insert_one({"guild_id": ctx.guild.id, "_id": channel.id})
            await ctx.send(f"{channel} has been added to ignore commands list.", delete_after=5)
        else:
            self.db.delete_one({"guild_id": ctx.guild.id, "_id": channel.id})
            await ctx.send(f"{channel} has been removed from ignore commands list.", delete_after=5)
        self.update(ctx.guild.id)


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs. This will update Ignore's data from mongoDB.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    temp = Ignore(bot)
    temp.update()
    bot.add_cog(temp)
    bot.ignore_check = temp.ignore_check
    print("Load Cog:\tIgnore")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("Ignores")
    bot.ignore_check = offline
    print("Unload Cog:\tIgnore")


def offline(ctx: commands.Context, ignore_dm: bool = False):
    """
    A function that checks if DM is ignored. This is only used when Ignore Cog is offline.

    Parameters
    ----------
    ctx : commands.Context
        pass in context for analysis
    ignore_dm : bool
        whether or not the command is being ignored in direct messages

    Returns
    -------
    bool
        Whether or not that channel is ignored
    """
    if not ctx.guild:
        return ignore_dm

    return False
