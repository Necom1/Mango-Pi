import typing
import asyncio
import discord
import datetime
from discord.ext import commands
from misc.Blueprints import DelayedTask, time_converter


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs. This function also populates the Cog with temporary ban data.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(Removal(bot))
    print("Load Cog:\tRemoval")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("Removal")
    print("Unload Cog:\tRemoval")


async def ban_over(bot: commands.Bot, guild_id: int, user_id: int, reason: str, late: bool = False):
    """
    Function that will attempt to unban a temporary banned user from the specified server. This function will also
    do some database clean up.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot for database and Cog access
    guild_id : int
        ID of the server user is temporary banned in
    user_id : int
        ID of the banned user
    reason : str
        reason of the initial ban
    late : bool
        whether or not the unban is late
    """
    guild = bot.get_guild(guild_id)
    if not guild:
        try:
            bot.mongo["temp_ban"].delete_many({"guild_id": guild_id})
            bot.get_cog("Removal").temp_bans.pop(guild_id)
        except KeyError:
            pass
        return
    user = bot.get_user(user_id)
    if not user:
        try:
            user = await bot.fetch_user(user_id)
        except discord.NotFound:
            try:
                bot.mongo["temp_ban"].delete_one({"guild_id": guild_id, "user_id": user_id})
                bot.get_cog("Removal").temp_bans[guild_id].pop(user_id)
            except KeyError:
                pass
            return
    if late:
        reason += "\nWarning: Late ban due to Cog downtime"
    await guild.unban(user, reason=reason)


class TemporaryBan(DelayedTask):
    """
    Class inherited from DelayedTask. Holds function necessary for temporary ban.

    Attributes
    ----------
    bot : commands.Bot
        bot reference for handling database
    reason : str
        temporary ban reason
    user_id : int
        banned user ID
    guild_id : int
        the ID of the server user banned in
    identity : int
        ID of the temporary ban (command invoke message based)
    """

    def __init__(self, bot: commands.Bot, me: int = None, guild_id: int = None, user_id: int = None,
                 end: datetime.datetime = None, reason: str = "", pack: dict = None):
        """
        Constructor for TemporaryBan class which also starts the temporary ban timer.

        Parameters
        ----------
        bot : commands
            pass in bot reference
        me : int
            the temporary ban ID (decided by ID of the message invoking temp_ban command
        guild_id : int
            server ID of the temporary ban
        user_id : int
            ID of the user being temporary banned
        end : datetime.datetime
            when the ban ends
        reason : str
            ban reason
        pack
            pass in package from database if initialized from update method
        """
        self.bot = bot
        if pack:
            self.reason = pack["reason"]
            self.user_id = pack["user_id"]
            self.guild_id = pack["guild_id"]
            self.identity = pack["_id"]
            DelayedTask.__init__(self, pack["end"])
        else:
            self.reason = reason
            self.user_id = user_id
            self.identity = me
            self.guild_id = guild_id
            DelayedTask.__init__(self, end)
        self.begin()

    async def on_exit(self):
        """
        Method that will be called upon exiting the current task.
        """
        try:
            self.bot.get_cog("Removal").temp_bans[self.guild_id].pop(self.user_id)
            self.bot.mongo["temp_ban"].delete_one({"_id": self.identity})
        except KeyError:
            pass

    async def task(self):
        """
        Method of the delayed task which will automatically unban the user on the specified time.
        """
        await asyncio.sleep(self.seconds)
        await ban_over(self.bot, self.guild_id, self.user_id, self.reason)
        await self.on_exit()


class Removal(commands.Cog):
    """
    Class inherited from commands.Cog that contains user removal commands.

    Attributes
    ----------
    bot : commands.Bot
        bot reference
    db : MongoClient
        mongoDB client pointing to "reminders" collection
    temp_bans : dict
        dictionary of all the temporary bans
    """

    def __init__(self, bot: commands.Bot):
        """
        Constructor for Removal class.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference
        """
        self.bot = bot
        self.temp_bans = {}
        self.db = bot.mongo["temp_ban"]
        self.update()

    def update(self):
        """
        Method that will populate the temp_ban dictionary with temporary ban from database. Recommended to call upon
        loading Cog.
        """
        late_bans = []
        self.temp_bans.clear()
        data = self.db.find()
        for i in data:
            try:
                self.temp_bans[i['guild_id']]
            except KeyError:
                self.temp_bans.update({i['guild_id']: {}})
            try:
                insert = TemporaryBan(bot=self.bot, pack=i)
            except ValueError:
                late_bans.append(i)
                self.db.delete_one({"_id": i['_id']})
            else:
                self.temp_bans[i['guild_id']].update({i['user_id']: insert})
        for i in late_bans:
            asyncio.get_event_loop().create_task(ban_over(self.bot, i["guild_id"], i["user_id"], i["reason"], True))

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, targets: commands.Greedy[discord.Member],
                   acknowledgement: typing.Optional[bool] = False, *, args: str = "No reason"):
        """Kick the specified members from the server."""
        # Reference: https://discordpy.readthedocs.io/en/latest/ext/commands/commands.html
        if len(targets) == 0 and len(targets) > 1:
            return await ctx.send("Can not locate any kick targets. "
                                  "Please make sure they are currently members of this server.")

        reason = f'{ctx.author}[{ctx.author.id}]: "{args}"'

        if not acknowledgement:
            valid = ["✅", "🇽"]

            def sure(reaction1: discord.Reaction, user1: discord.User):
                return user1.id == ctx.author.id and reaction1.message.id == message.id \
                       and str(reaction1.emoji) in valid

            embed = discord.Embed(
                title="Kick Confirmation",
                colour=0xfbc531
            )
            mems = ""
            for i in range(len(targets)):
                mems += f"{i + 1}. {targets[i].mention}\n"
            embed.add_field(name="Pending Kicks", value=mems, inline=False)
            embed.add_field(name="Kick Reason", value=reason, inline=False)
            embed.set_footer(icon_url=ctx.author.avatar_url_as(size=64),
                             text=f"Kicking total of {len(targets)} members")
            message = await ctx.send(embed=embed)
            for i in valid:
                await message.add_reaction(emoji=i)

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=sure)
            except asyncio.TimeoutError:
                await message.edit(embed=None, content="Kick Confirmation Menu Timeout")
                return await message.clear_reactions()
            else:
                if reaction.emoji == "🇽":
                    return await message.delete()
                else:
                    await message.delete()

        for i in targets:
            await ctx.guild.kick(i, reason=reason)

        await ctx.message.add_reaction(emoji='✅')

    @kick.error
    async def kick_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        Async method called when bot experiences error from using kick command.

        Parameters
        ----------
        ctx : commands.Context
            passed in context for analysis and reply
        error : commands.CommandError
            error encountered

        Returns
        -------
        discord.Message
            processed error message sent back to context channel
        """
        nope = self.bot.ignore_check(ctx)
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("Make sure to specify the target user to kick.", delete_after=10)
        elif isinstance(error, commands.BadArgument):
            return await ctx.send("Improper usage of clear command.", delete_after=10)
        elif isinstance(error, discord.Forbidden):
            if nope:
                return
            embed = discord.Embed(
                title="😔 Not Enough Permission", colour=0xf9ca24,
                description="I don't have the permission required to perform a kick. To do this, I will need: "
                            "**Kick Members** permission."
            )
            return await ctx.send(embed=embed, delete_after=10)
        elif isinstance(error, commands.MissingPermissions):
            if nope:
                return
            embed = discord.Embed(
                title="👮 No Permission", colour=0x34ace0,
                description='You will need the permission of [Kick Members] to use this command.'
            )
            embed.set_footer(text=f"Input by {ctx.author}", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed, delete_after=10)
        else:
            await ctx.send("Unknown error has occurred, please try again later.", delete_after=10)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, targets: commands.Greedy[discord.Member],
                  delete_days: typing.Optional[int] = 0, acknowledgement: typing.Optional[bool] = False, *,
                  args: str = "No reason"):
        """Command to ban the specified members from the server."""
        # Reference: https://discordpy.readthedocs.io/en/latest/ext/commands/commands.html
        if delete_days > 7:
            delete_days = 7
        if len(targets) == 0:
            return await ctx.send("Can not locate any ban targets. "
                                  "Please make sure they are currently members of this server.")

        reason = f'{ctx.author}[{ctx.author.id}]: "{args}"'

        if not acknowledgement and len(targets) > 1:
            valid = ["✅", "🇽"]

            def sure(reaction1: discord.Reaction, user1: discord.User):
                return user1.id == ctx.author.id and reaction1.message.id == message.id \
                       and str(reaction1.emoji) in valid

            embed = discord.Embed(
                title="Ban Confirmation",
                colour=0xe84118
            )
            mems = ""
            for i in range(len(targets)):
                mems += f"{i + 1}. {targets[i].mention}\n"
            embed.add_field(name="Pending Bans", value=mems, inline=False)
            embed.add_field(name="Ban Reason", value=reason, inline=False)
            embed.set_footer(icon_url=ctx.author.avatar_url_as(size=64),
                             text=f"Remove Messages from the past {delete_days} days")
            message = await ctx.send(embed=embed)
            for i in valid:
                await message.add_reaction(emoji=i)

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=sure)
            except asyncio.TimeoutError:
                await message.edit(embed=None, content="Ban Confirmation Menu Timeout")
                return await message.clear_reactions()
            else:
                if reaction.emoji == "🇽":
                    return await message.delete()
                else:
                    await message.delete()

        for i in targets:
            await ctx.guild.ban(i, delete_message_days=delete_days, reason=reason)

        await ctx.message.add_reaction(emoji='✅')

    @commands.command(aliases=["idban", "IDBan"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def id_ban(self, ctx: commands.Context, target: typing.Union[discord.Member, discord.User, int],
                     delete_days: typing.Optional[int] = 0, *, reason: str = "No reason"):
        """Ban a user from the server by their discord ID"""
        reason = f'{ctx.author}[{ctx.author.id}]: "{reason}"'
        if isinstance(target, int):
            target = await self.bot.fetch_user(target)
        await ctx.guild.ban(target, delete_message_days=delete_days, reason=reason)
        await ctx.message.add_reaction(emoji='✅')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def soft_ban(self, ctx: commands.Context, target: discord.Member, delete_days: typing.Optional[int] = 0, *,
                       args: str = "No reason"):
        """Remove all specified days of recent messages from the user while removing them from the server"""
        args = f'{ctx.author}[{ctx.author.id}] Soft ban for: "{args}" with removal of {delete_days} day of messages.'
        await ctx.guild.ban(target, reason=args, delete_message_days=delete_days)
        await ctx.guild.unban(target, reason=args)
        await ctx.message.add_reaction(emoji='✅')

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """
        Event listener that triggers when bot detects an unban. Bot will scan to see if that user is part of the
        temporary ban list and take appropriate action.

        Parameters
        ----------
        guild : discord.Guild
            server of the unban
        user : discord.User
            the user being unbanned
        """
        try:
            data = self.temp_bans[guild.id][user.id]
        except KeyError:
            return
        else:
            await data.terminate()

    @commands.command(aliases=['tban'])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def temporary_ban(self, ctx: commands.Context, target: typing.Union[discord.Member, discord.User, int],
                            duration: str, *, reason: str = "No reason"):
        """Command to temporary ban a user for set number of days"""
        if len(reason) > 1000:
            return await ctx.send("Too long of a ban reason... Try keep it under 1000 letters...")

        try:
            time = time_converter(duration, ctx.message.created_at)
        except ValueError as e:
            return await ctx.send(str(e.args[0]))

        try:
            self.temp_bans[ctx.guild.id]
        except KeyError:
            self.temp_bans.update({ctx.guild.id: {}})

        if isinstance(target, int):
            try:
                target = await self.bot.fetch_user(target)
            except discord.NotFound:
                return await ctx.send("Can not find that user.")

        index = target.id
        is_new = False

        try:
            data = self.temp_bans[ctx.guild.id][index]
        except KeyError:
            is_new = True
            if duration.startswith('-'):
                return await ctx.send("User is not temporary banned, unable to remove duration.")
            reason = f"Temporary ban until {time.strftime('%B %#d, %Y | `%I:%M %p` UTC')} for:\n **{reason}**"
            data = TemporaryBan(self.bot, ctx.message.id, ctx.guild.id, index, time, reason)
            self.temp_bans[ctx.guild.id].update({index: data})
            time = data.end
        else:
            try:
                time = time_converter(duration, data.end)
            except ValueError as e:
                return await ctx.send(str(e.args[0]))
            await data.terminate()
            reason = f"Temporary ban until {time.strftime('%B %#d, %Y | `%I:%M %p` UTC')} for:\n **{reason}**"
            try:
                new = TemporaryBan(self.bot, ctx.message.id, ctx.guild.id, index, time, reason)
            except ValueError:
                await ban_over(self.bot, ctx.guild.id, index, f"{reason}\nUnbanned after time re-calculation")
                return await ctx.send("User unbanned after time re-calculation")
            self.temp_bans[ctx.guild.id].update({index: new})

        try:
            await ctx.guild.fetch_ban(target)
        except discord.NotFound:
            await ctx.guild.ban(target, reason=reason)
        self.db.insert_one({"_id": ctx.message.id, "guild_id": ctx.guild.id, "user_id": index, "end": time,
                            "reason": reason})

        if is_new:
            title = "New Temporary Ban Timer"
            color = 0xe74c3c
        else:
            title = "Updated Temporary Ban Timer"
            color = 0xff9f43

        embed = discord.Embed(
            timestamp=time,
            colour=color
        ).set_author(icon_url=str(target.avatar_url_as(size=64)), name=title)
        embed.add_field(name="Expected unban time: ", value=time.strftime('%B %#d, %Y | `%I:%M %p` UTC'))
        embed.set_footer(text="Unban ")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, target: typing.Union[int, discord.User], *, reason: str = "Not specified"):
        """Unban the specified user from the server"""
        # https://stackoverflow.com/questions/55742719/is-there-a-way-i-can-unban-using-my-discord-py-rewrite-bot
        reason = f"{reason}\n |=> {ctx.author}[{ctx.author.id}]"
        if isinstance(target, int):
            member = await self.bot.fetch_user(target)
        else:
            member = target
        await ctx.message.guild.unban(user=member, reason=reason)
        await ctx.message.add_reaction(emoji='✅')

    @commands.command(aliases=['tbl'])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def temporary_ban_list(self, ctx: commands.Context, page: int = 1):
        """Return a list of temporarily banned users (that is under bot's system)"""
        if page <= 0:
            return await ctx.send("Page number can't be less than 1")
        try:
            data = list(self.temp_bans[ctx.guild.id].values())
            if len(data) == 0:
                raise KeyError("empty")
        except KeyError:
            return await ctx.send("No temporary bans that I am aware of.")

        limit = 5
        total_page = (len(data) // limit) + 1
        start = 0 if page == 1 else (limit * (page - 1))
        end = len(data) if start + limit >= len(data) else start + limit

        embed = discord.Embed(
            colour=0xa29bfe,
            timestamp=ctx.message.created_at
        ).set_author(name="Temporary Ban List", icon_url=ctx.guild.icon_url)
        embed.set_footer(text=f"Page {page} / {total_page}")

        for i in range(start, end):
            embed.add_field(name=f"User ID: {data[i].user_id}",
                            value=f"__<@!{data[i].user_id}>__\n{data[i].reason}", inline=False)

        await ctx.send(embed=embed)

    @ban.error
    @id_ban.error
    @soft_ban.error
    @temporary_ban.error
    async def ban_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        Listener method to be called upon when an error occurs during any ban commands.

        Parameters
        ----------
        ctx : commands.Context
            pass in context for error analysis
        error : commands.CommandError
            the error that has occurred

        Returns
        -------
        discord.Message
            return the "error" message sent back to the user
        """
        nope = self.bot.ignore_check(ctx)
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("Make sure to specify the target user to ban.", delete_after=10)
        elif isinstance(error, commands.BadArgument):
            return await ctx.send("Improper usage of ban command.", delete_after=10)
        elif isinstance(error, discord.Forbidden):
            if nope:
                return
            embed = discord.Embed(
                title="😔 Not Enough Permission", colour=0xf9ca24,
                description="I don't have the permission required to ban members. To do this, I will need: "
                            "**Ban Members** permission."
            )
            return await ctx.send(embed=embed, delete_after=10)
        elif isinstance(error, commands.MissingPermissions):
            if nope:
                return
            embed = discord.Embed(
                title="👮 No Permission", colour=0x34ace0,
                description='You will need the permission of [Ban Members] to use this command.'
            )
            embed.set_footer(text=f"Input by {ctx.author}", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed, delete_after=10)
        elif isinstance(error, discord.NotFound):
            return await ctx.send("Can not find target user. Please double check the ID you entered.", delete_after=10)
        else:
            await ctx.send("Unknown error has occurred, please try again later.", delete_after=10)
