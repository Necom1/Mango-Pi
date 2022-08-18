import typing
import asyncio
import discord
from discord.ext import commands
from Components.MangoPi import MangoPi, is_admin


async def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog
    """
    await bot.add_cog(BotConfig(bot))
    print("Load Cog:\tBotConfig")


async def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog
    """
    await bot.remove_cog("BotConfig")
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
        Constructor for BotConfig class

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

    async def rsa_toggle(self, message: discord.Message, mode: int):
        """
        Async method that reverses the boolean variable of the rsa based on the passed in mode and react to the passed
        in message appropriately to indicate it's new state

        Parameters
        ----------
        message: discord.Message
            the discord Message to react the new result to
        mode: int
            which part of the array data to flip the boolean
        """
        self.bot.data.rsa[mode] = not self.bot.data.rsa[mode]
        await message.add_reaction(emoji="🟢" if self.bot.data.rsa[mode] else "🔴")
        self.bot.data.settings_db_update("rsa")

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
        """
        Group command for log report, no sub-command invoke will bring up list of channels and user to report to.
        """
        if not ctx.invoked_subcommand:
            temp = self.bot.data.console_data()

            dm, channels = [], []

            emotes = ('🤖', '💬', '⚠')

            for k, v in temp.items():

                result = ''
                for z in range(1, 4):
                    result += emotes[z-1] if v[z] else '🔴'
                if v[0]:
                    channels.append(f"{result} <#{k}>")
                else:
                    dm.append(f"{result} <@!{k}>")

            embed = discord.Embed(
                title="Bot Consoles",
                colour=0x6c5ce7,
                timestamp=ctx.message.created_at
            )

            if len(dm) > 0:
                temp = "\n".join(dm)
                embed.add_field(inline=False, name="DMs", value=temp)
            if len(channels) > 0:
                temp = "\n".join(channels)
                embed.add_field(inline=False, name="Text Chats", value=temp)

            await ctx.reply(embed=embed)

    @log_report.command(aliases=["+"])
    async def add(self, ctx: commands.Context, new: typing.Union[discord.User, discord.TextChannel] = None):
        """log_report sub-command for adding a user or channel to log report list base on passed in types."""
        if not new:
            new = ctx.author if not ctx.guild else ctx.channel

        if not self.bot.data.is_in_console(new):
            self.bot.data.modify_console(new, [False, False, False])
        else:
            return await ctx.reply(f"{new.mention} is already within the log report list")

        await ctx.message.add_reaction(emoji="✅")

    @log_report.command(aliases=['m'])
    async def modify(self, ctx: commands.Context, exist: typing.Union[discord.User, discord.TextChannel, int] = None):
        """log_report sub-command for modifying an existing console channel"""
        if not exist:
            exist = ctx.author if not ctx.guild else ctx.channel

        data = self.bot.data.console_data(exist if isinstance(exist, int) else exist.id)
        if not data:
            return await ctx.reply("Can not find the specified target")

        temp = f"🤖 |=> {'🟢' if data[1] else '🔴'} |=> Normal Bot Status Reports\n" \
               f"💬 |=> {'🟢' if data[2] else '🔴'} |=> Chat Messages\n" \
               f"⚠ |=> {'🟢' if data[3] else '🔴'} |=> Errors"

        embed = discord.Embed(
            color=ctx.author.colour,
            title="React to modify",
            description=temp
        )
        embed.set_author(name=f"{exist} console settings")
        embed.add_field(name="Freezing", value="reacting with '⏸' will freeze this menu")
        embed.set_footer(text=f"react with '❌' to delete {exist} console")

        msg = await ctx.reply(embed=embed)
        reactions = ('🤖', '💬', '⚠', '⏸', '❌')

        for i in reactions:
            await msg.add_reaction(emoji=i)

        def check(reaction1: discord.Reaction, user1: discord.User):
            return (reaction1.message.id == msg.id) and (user1.id == ctx.author.id) and \
                   str(reaction1.emoji) in reactions

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=check)
        except asyncio.TimeoutError:
            await msg.edit(embed=None, content=f"**{exist}** console setting menu timed out ⏱")
            await msg.clear_reactions()
        else:
            if reaction.emoji == '❌':
                try:
                    self.bot.data.remove_console(exist)
                    await msg.edit(content="Deleted!", embed=None)
                except ValueError:
                    await msg.edit(content=f"{exist.mention} not found within the log report list", embed=None)
            elif reaction.emoji == '⏸':
                embed.remove_field(0)
                embed.set_footer(text="Frozen")
                embed.title = None
                embed.timestamp = msg.created_at
                await msg.edit(embed=embed)
            else:
                temp = ('🤖', '💬', '⚠')  # + 1 for original index
                try:
                    update = temp.index(reaction.emoji)
                except ValueError:
                    await msg.edit(content="Unknown reaction applied, operation terminated.", embed=None)
                else:
                    data[update+1] = not data[update+1]
                    self.bot.data.modify_console(exist, [data[1], data[2], data[3]])
                    temp = f"🤖 |=> {'🟢' if data[1] else '🔴'} |=> Normal Bot Status Reports\n" \
                           f"💬 |=> {'🟢' if data[2] else '🔴'} |=> Chat Messages\n" \
                           f"⚠ |=> {'🟢' if data[3] else '🔴'} |=> Errors"
                    embed.description = temp
                    embed.remove_field(0)
                    embed.set_footer(text="Updated")
                    embed.title = None
                    embed.timestamp = msg.created_at
                    await msg.edit(embed=embed)

            await msg.clear_reactions()
        # TODO finish this (merge remove?)

    @commands.group(aliases=["sa"])
    @commands.check(is_admin)
    async def status_activity(self, ctx: commands.Context):
        """
        Group command for default status and activities, no sub-command will bring up bot status and activity menu.
        """
        if self.bot.data.rsa[0]:
            return await ctx.reply("Random Status and Activity is on, please turn it off before trying to modify "
                                   "default bot status and activity")

        if not ctx.invoked_subcommand:
            status_emote = {
                "online": "🟢",
                "idle": "🌙",
                "dnd": "🔴",
                "invisible": "👻"
            }
            data = self.bot.data.status

            embed = discord.Embed(
                colour=0x0abde3,
                title="Bot Discord Status and Activity"
            )

            embed.add_field(inline=False, name="Status", value=f"{status_emote[data[0]]} - {data[0]}")
            embed.add_field(inline=False, name="Activity", value=f"{data[1]}ing **__{data[2]}__**")
            await ctx.reply(embed=embed)

    @status_activity.command(aliases=["s", "stat"])
    async def status(self, ctx: commands.Context, *, new: str):
        """
        Sub-command of status_activity command that takes in passed in status and changes the current bot status.
        """
        if new in ("online", "green"):
            result = "online"
        elif new in ("idle", "moon", "yellow"):
            result = "idle"
        elif new in ("do not disturb", "dnd", "red"):
            result = "dnd"
        elif new in ("invisible", "grey", "gray"):
            result = "invisible"
        else:
            return await ctx.reply("Unknown parameter inputted, try do it by color and know that this is space "
                                   "sensitive")

        self.bot.data.status[0] = result
        self.bot.data.settings_db_update("status")
        await self.bot.data.change_to_default_activity()
        await ctx.message.add_reaction(emoji="✅")

    @status_activity.command(aliases=["at"])
    async def activity_type(self, ctx: commands.Context, new: str):
        """
        Sub-command of status_activity command that takes in passed in activity type and change the current bot
        activity.
        """
        if new.endswith("ing"):
            new = new[:-3]
        if new not in ("play", "listen", "watch", "stream"):
            return await ctx.reply("Unknown input, please check activity type and try again")

        self.bot.data.status[1] = new
        self.bot.data.settings_db_update("status")
        await self.bot.data.change_to_default_activity()
        await ctx.message.add_reaction(emoji="✅")

    @status_activity.command(aliases=["a"])
    async def activity(self, ctx: commands.Context, *, new: str = ""):
        """
        Sub-command of status_activity command that takes in passed in string and change current bot activity. If no
        string given, bot activity will be set to none.
        """
        self.bot.data.status[2] = new
        self.bot.data.settings_db_update("status")
        await self.bot.data.change_to_default_activity()
        await ctx.message.add_reaction(emoji="✅")

    @commands.group(aliases=["rsa"])
    @commands.check(is_admin)
    async def random_status_activity(self, ctx: commands.Context):
        """
        Group command for random status and activities, no sub-command invoke will bring up list RSA status menu.
        """
        if not ctx.invoked_subcommand:
            desc = ("🟢" if self.bot.data.rsa[1] else "🔴") + " Random Status\n"
            desc += ("🟢" if self.bot.data.rsa[2] else "🔴") + " Random Activity Type\n"
            desc += ("🟢" if self.bot.data.rsa[3] else "🔴") + " Random Activities\n"
            desc += f"**Delay / Interval**: {self.bot.data.rsa[4]} seconds"

            embed = discord.Embed(
                colour=0x32ff7e if self.bot.data.rsa[0] else 0xff3838,
                title="Random Status and Activities Menu",
                description=desc
            )

            if len(self.bot.data.activities) > 0:
                more = [f"> {i}" for i in self.bot.data.activities]
                embed.add_field(inline=False, name="Activities", value="\n".join(more))

            await ctx.reply(embed=embed)

    @random_status_activity.command()
    async def toggle(self, ctx: commands.Context):
        """
        Sub-command of rsa command, switches on or off the RSA system base on it's current status.
        """
        self.bot.data.rsa[0] = not self.bot.data.rsa[0]
        self.bot.data.settings_db_update("rsa")
        if self.bot.data.rsa[0]:
            self.bot.data.rsa_process.start()
            await ctx.reply("Random Status and Activity now **On**")
        else:
            self.bot.data.rsa_process.stop()
            await ctx.reply("Random Status and Activity is now **Off**")
        await self.bot.data.change_to_default_activity()

    @random_status_activity.command(aliases=["status"])
    async def s(self, ctx: commands.Context):
        """Sub-command of rsa command, toggles RSA system status setting on or off."""
        await self.rsa_toggle(ctx.message, 1)

    @random_status_activity.command(aliases=["activity_type"])
    async def at(self, ctx: commands.Context):
        """Sub-command of rsa command, toggles RSA system activity_type setting on or off."""
        await self.rsa_toggle(ctx.message, 2)

    @random_status_activity.command(aliases=["activity"])
    async def a(self, ctx: commands.Context):
        """Sub-command of rsa command, toggles RSA system activity setting on or off."""
        await self.rsa_toggle(ctx.message, 3)

    @random_status_activity.command(aliases=["t"])
    async def timer(self, ctx: commands.Context, seconds: int = 10):
        """Sub-command of rsa command, takes in integer input for the interval for the RSA system."""
        if seconds < 10:
            return await ctx.reply("Timer for RSA can't be less than 10 seconds")
        if self.bot.data.rsa[4] == seconds:
            return await ctx.reply("No changes has been made")
        self.bot.data.rsa[4] = seconds
        self.bot.data.settings_db_update("rsa")
        await ctx.message.add_reaction(emoji="✅")

    @random_status_activity.command(aliases=["+"])
    async def add_activity(self, ctx: commands.Context, *, new: str):
        """Sub-command of rsa command, adds new activity into the RSA system."""
        if new in self.bot.data.activities:
            return await ctx.reply("That activity already exist within the RSA system")
        self.bot.data.add_activity(new)
        await ctx.message.add_reaction(emoji="✅")

    @random_status_activity.command(aliases=["-"])
    async def remove_activity(self, ctx: commands.Context, *, exist: str):
        """Sub-command of rsa command, remove existing activity from the RSA system."""
        if exist not in self.bot.data.activities:
            return await ctx.reply("That activity can not be found within the RSA system")
        self.bot.data.remove_activity(exist)
        await ctx.message.add_reaction(emoji="✅")

    @random_status_activity.command(aliases=["l"])
    async def list(self, ctx: commands.Context, page: int = 1):
        """Sub-command of rsa command, listen all activities stored in the RSA system."""
        data = self.bot.data.activities

        if len(data) == 0:
            await ctx.reply("There is no stored activity")
        else:
            mini = (page - 1) * 10
            maxi = page * 10
            ret = ""

            if maxi > len(data):
                maxi = len(data)
            for i in range(mini, maxi):
                ret += f"{i + 1}. **{data[i]}**\n"

            embed = discord.Embed(
                description=ret,
                colour=0x1dd1a1,
                title="Activities For RSA"
            )
            embed.set_footer(icon_url=self.bot.user.avatar.replace(size=64).url,
                             text=f"{page} / {int((len(data) // 10)) + 1} Pages")

            await ctx.reply(embed=embed)
