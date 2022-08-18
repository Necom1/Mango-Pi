import discord
from discord.ext import commands
from Components.MangoPi import MangoPi


async def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs. This will update Prefix's data from mongoDB and append get_prefix to
    bot command_prefix.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog and modify command_prefix
    """
    temp = Prefix(bot)
    temp.update()
    await bot.add_cog(temp)
    bot.command_prefix = temp.get_prefix
    print("Load Cog:\tPrefix")


async def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog. This will restore bot command_prefix to bot default.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog and restore command_prefix
    """
    bot.command_prefix = commands.when_mentioned_or(bot.default_prefix)
    await bot.remove_cog("Prefix")
    print("Unload Cog:\tPrefix")


class Prefix(commands.Cog):
    """
    Class inherited from commands.Cog that allows servers to set custom prefix for the bot.

    Attributes
    ----------
    bot : MangoPi
        MangoPi bot reference
    prefix : dict
        dictionary that stores all the prefixes
    db : MongoClient
        client for MongoDB "custom_prefix" collection
    """
    def __init__(self, bot: MangoPi):
        """
        Constructor for Prefix class.

        Parameters
        ----------
        bot : MangoPi
            pass in bot reference for the Cog
        """
        self.bot = bot
        self.prefix = {}
        self.db = bot.mongo["prefix"]

    # method to pass into bot command_prefix
    def get_prefix(self, client: MangoPi, message: discord.Message):
        """
        Method that design to be pass into commands.Bot's command_prefix

        Parameters
        ----------
        client : MangoPi
            bot reference for commands.when_mentioned_or
        message : discord.Message
            The Received discord message

        Returns
        -------
        commands.when_mentioned_or
            Method to pass into bot.command_prefix
        """
        default = client.default_prefix

        try:
            if not message.guild:
                raise KeyError("default")
                
            prefix = self.prefix[message.guild.id]
            
            if not prefix:
                raise KeyError("default")
        except KeyError:
            return commands.when_mentioned_or(default)(client, message)

        # custom prefix
        return commands.when_mentioned_or(prefix)(client, message)

    def update(self):
        """
        Method that updates prefix dictionary from mongoDB.
        """
        self.prefix.clear()
        data = self.db.find({})
        for i in data:
            self.prefix.update({i['_id']: i['prefix']})

    # change prefix for the guild
    @commands.group()
    @commands.guild_only()
    async def prefix(self, ctx: commands.Context):
        """Command that will display the prefix setting for the current server with no additional parameter."""
        if not ctx.invoked_subcommand:
            if self.bot.ignore_check(ctx):
                return
            # if no sub-command specified, reply with the current server prefix setting
            try:
                data = self.prefix[ctx.guild.id]
            except KeyError:
                data = None

            if data is None:
                await ctx.reply(f"The default **{self.bot.default_prefix}**")
            else:
                await ctx.reply(f"Prefix for this server is **{data}**")

    @prefix.command()
    async def default(self, ctx: commands.Context):
        """Command that display bot default prefix."""
        await ctx.reply(f"My default prefix is: **{self.bot.default_prefix}**")

    @prefix.command()
    @commands.has_permissions(manage_channels=True)
    async def set(self, ctx: commands.Context, pre: str):
        """Sub-command of prefix that changes the server prefix."""
        # find server prefix
        try:
            data = self.prefix[ctx.guild.id]
        except KeyError:
            data = None

        if pre == self.bot.default_prefix:
            # resetting prefix to bot default
            if not data:
                # if no server prefix setting
                await ctx.reply("🤷 Nothing has changed.")
            else:
                # resetting current prefix back to default
                self.db.delete_one({"_id": ctx.guild.id})
                self.prefix.pop(ctx.guild.id)
                await ctx.reply(f"Server prefix have been reset to: **{self.bot.default_prefix}**.")
            return

        if not data:
            # inserts the new prefix setting over the default
            self.db.insert_one({"_id": ctx.guild.id, "prefix": pre})
            self.prefix.update({ctx.guild.id: pre})
            await ctx.reply(f"Server prefix have been set to: ** {pre} **.")
        else:
            # changing the current prefix setting
            self.db.update_one({"_id": ctx.guild.id}, {"$set": {"prefix": pre}})
            self.prefix[ctx.guild.id] = pre
            await ctx.reply(f"Server prefix have been updated to: ** {pre} **.")
