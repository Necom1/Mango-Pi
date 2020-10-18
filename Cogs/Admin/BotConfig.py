import typing
import asyncio
import discord
from discord.ext import commands
from Components.MangoPi import MangoPi, is_admin


def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog
    """
    bot.add_cog(BotConfig(bot))
    print("Load Cog:\tBotConfig")


def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog
    """
    bot.remove_cog("BotConfig")
    print("Unload Cog:\tBotConfig")


class BotConfig(commands.Cog):
    """
    Class inherited from commands.Cog that contains Cog management commands for managing some bot settings.

    Attributes
    ----------
    bot : MangoPi
        MangoPi Bot reference
    follow_up : bool
        whether or not bot need follow up status change after the bot is ready
    """

    def __init__(self, bot: MangoPi):
        """
        Constructor for BotCofig class

        Parameters
        ----------
        bot: MangoPi
            takes in MangoPi reference
        """
        self.bot = bot
        self.follow_up = False

        if self.bot.is_ready():
            asyncio.get_event_loop().create_task(self.bot.data.change_to_default_activity())
        else:
            self.follow_up = True

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Async event listener executes when bot is ready, checks whether or not bot need presence change follow up
        """
        if self.follow_up:
            await self.bot.data.change_to_default_activity()

    @commands.group(aliases=["lr"])
    @commands.check(is_admin)
    async def log_report(self, ctx: commands.Context):
        """Group command for log report, no sub-command invoke will bring up list of channels and user to
        report to"""
        if not ctx.invoked_subcommand:
            dm = [f"<@!{i}>" for i in self.bot.data.console_dm]
            channels = [f"<#{i}>" for i in self.bot.data.console_channels]

            embed = discord.Embed(
                title="Log Report to",
                colour=0x6c5ce7,
                timestamp=ctx.message.created_at
            )

            if len(dm) > 0:
                embed.add_field(inline=False, name="DM User", value="\n".join(dm))
            if len(channels) > 0:
                embed.add_field(inline=False, name="Console Channels", value="\n".join(channels))

            await ctx.send(embed=embed)

    @log_report.command(aliases=["+"])
    async def add(self, ctx: commands.Context, new: typing.Union[discord.User, discord.TextChannel] = None):
        """log_report sub-command for adding a user or channel to log report list base on passed in types"""
        if not new:
            new = ctx.author if not ctx.guild else ctx.channel

        try:
            self.bot.data.add_console(new)
        except ValueError:
            return await ctx.send(f"{new.mention} is already within the log report list")

        try:
            self.bot.data.save()
        except RuntimeError:
            self.bot.data.remove_console(new)
            return await ctx.send("System currently busy, try again later")

        await ctx.message.add_reaction(emoji="✅")

    @log_report.command(aliases=["-"])
    async def remove(self, ctx: commands.Context, exist: typing.Union[discord.User, discord.TextChannel, int] = None):
        """log_report sub-command for removing an existing user or channel from log report list base on passed in types
        """
        if not exist:
            exist = ctx.author if not ctx.guild else ctx.channel

        try:
            self.bot.data.remove_console(exist)
        except ValueError:
            return await ctx.send(f"{exist.mention} not found within the log report list")

        try:
            self.bot.data.save()
        except RuntimeError:
            self.bot.data.add_console(exist)
            return await ctx.send("System currently busy, try again later")

        await ctx.message.add_reaction(emoji="🗑️")

    @commands.group(aliases=["rsa"])
    async def random_status_activity(self, ctx: commands.Context):
        """Group command for random status and activities, no sub-command invoke will bring up list RSA status menu"""
        if not ctx.invoked_subcommand:
            desc = ("🟢" if self.bot.data.rsa[1] else "🔴") + " Random Status\n"
            desc += ("🟢" if self.bot.data.rsa[2] else "🔴") + " Random Activities\n"
            desc += f"**Delay / Interval**: {self.bot.data.rsa[3]} seconds"

            embed = discord.Embed(
                colour=0x32ff7e if self.bot.data.rsa[0] else 0xff3838,
                title="Random Status and Activities Menu",
                description=desc
            )

            if len(self.bot.data.activities) > 0:
                more = [f"> {i}" for i in self.bot.data.activities]
                embed.add_field(inline=False, name="Activities", value="\n".join(more))

            await ctx.send(embed=embed)
