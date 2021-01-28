import typing
import asyncio
import discord
import datetime
from discord.ext import commands
from Components.MangoPi import MangoPi


def split_string(line: str, n: int):
    """
    Function that will split the given string into specified length and append it to array.

    Parameters
    ----------
    line : str
        the string to split
    n : int
        max length for the string

    Returns
    -------
    list
        list of the split string
    """
    # code from: https://stackoverflow.com/questions/9475241/split-string-every-nth-character
    return [line[i:i + n] for i in range(0, len(line), n)]


def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs. This will update Logging's data from mongoDB.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(Logging(bot))
    print("Load Cog:\tLogging")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog and restore command_prefix
    """
    bot.remove_cog("Logging")
    print("Unload Cog:\tLogging")


class Notify:
    """
    Class used to store information of a log channel.

    Attributes
    ----------
    guild : int
        server ID of the channel
    channel : int
        channel ID of the log channel
    data : dict
        dictionary storing booleans that dictates what information will show up on the log channel
    """

    def __init__(self, package: dict):
        """
        Constructor for Notify class.

        Parameters
        ----------
        package
            pass in mongoDB data
        """
        self.guild = package['guild_id']
        self.channel = package["_id"]
        self.data = {}
        temp = ['enter', 'leave', 'kick', 'ban', 'unban', 'trigger', 'raid', 'member_update', 'server_update',
                'vc_update']
        for i in temp:
            self.data.update({i: package[i]})


class Logging(commands.Cog):
    """
    Class inherited from commands.Cog that contains logging channel commands.

    Attributes
    ----------
    bot : commands.Bot
        commands.Bot reference
    db : MongoClient
        MongoDB client reference for "system_message" collection
    memory : dict
        dictionary containing list of logging channels for that server
    reactions : list
        list of reactions for the log channel setting menu
    label : dict
        dictionary of reaction and their meaning
    second : list
        list of check and cross emotes
    instance : list
        instances of setting menu
    """

    def __init__(self, bot: MangoPi):
        """
        Constructor for logging class

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference for the Cog
        """
        self.bot = bot
        self.memory = {}
        self.instance = []
        self.reactions = ["➡", "🚪", "👢", "🔨", "👼", "⚠", "🚶", "🔃", "🏗", "💬", "⏸", "❌"]
        self.label = {"➡": "enter", "🚪": "leave", "👢": "kick", "🔨": "ban", "👼": "unban", "⚠": "trigger",
                      "🚶": "raid", "🔃": "member_update", "🏗": "server_update", "💬": "vc_update"}
        self.second = ['✔', '🇽']
        self.db = bot.mongo["logging"]
        self.update()

    def find(self, guild: int, channel: int):
        """
        Method that scans memory for Notify of the specified server and channel.

        Parameters
        ----------
        guild : int
            Server the channel belongs to
        channel : int
            the target logging channel

        Returns
        -------
        Notify
            if the specified channel is a log channel
        None
            nothing is found with the specification within memory
        """
        try:
            for i in self.memory[guild]:
                if i.channel == channel:
                    return i
        except KeyError:
            pass

    def update(self, guild: int = None):
        """
        Method that updates memory data from MongoDB.

        Parameters
        ----------
        guild : int
            the specific server to update
        """
        if guild:
            try:
                self.memory.pop(guild)
            except KeyError:
                pass
            data = self.db.find({"guild_id": guild})
        else:
            self.memory.clear()
            data = self.db.find({})
        for i in data:
            try:
                fail = False
                server = self.bot.get_guild(i['guild_id'])
                if server:
                    chan = server.get_channel(i["_id"])
                    if not chan:
                        fail = True
                else:
                    fail = True

                if not fail:
                    self.memory[i['guild_id']].append(Notify(i))
                else:
                    self.db.delete_one({"guild_id": i['guild_id'], "_id": i["_id"]})
            except KeyError:
                self.memory.update({i['guild_id']: [Notify(i)]})

    @commands.group(aliases=["lc"])
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, view_audit_log=True)
    async def log_channels(self, ctx: commands.Context):
        """Command group of log channels. If no specific parameter received, bring up help menu."""
        if not ctx.invoked_subcommand:
            embed = discord.Embed(
                title="Sub-commands for log channels",
                colour=0xf39c12
            )
            embed.add_field(name="list", value="List channels that is set as a log channel")
            embed.add_field(name="+ (channel mention)",
                            value="Sets the current channel (if no channel is given) or the mentioned channel as a"
                                  "log channel")
            embed.add_field(name="s (channel mention)",
                            value="Opens up the setting menu for the mentioned or current channel.")
            embed.set_footer(icon_url=self.bot.user.avatar_url_as(size=64),
                             text="Now do the lc command followed by one of the above")

            await ctx.reply(embed=embed)

    @log_channels.command(aliases=["l"])
    async def list(self, ctx: commands.Context):
        """List the amount of log channels in the server."""
        try:
            data = self.memory[ctx.guild.id]
        except KeyError:
            await ctx.reply("This server don't have any log channel.")
            return

        message = "=========================\nList of log channels:\n-------------------------\n"
        for i in data:
            channel = ctx.guild.get_channel(i.channel)
            message += f"> {channel.mention}\n" if channel else f"> {i.channel} 🗑️\n"
        message += "========================="
        new = split_string(message, 2000)
        for i in new:
            await ctx.reply(i)

    @log_channels.command(aliases=["+", "a"])
    async def add(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set a new channel as a log channel."""
        channel = ctx.channel if not channel else channel
        data = self.find(ctx.guild.id, channel.id)

        if data:
            await ctx.reply(f"**#{channel}** is already a log channel.")
        else:
            f = False
            self.db.insert_one(
                {"guild_id": ctx.guild.id, "_id": channel.id, "leave": f, "enter": f, "kick": f, "ban": f,
                 "unban": f, "trigger": f, "raid": f, "member_update": f, "server_update": f, "vc_update": f}
            )
            self.update(ctx.guild.id)
            await ctx.reply(f"**#{channel}** has been set as a log channel")

    @log_channels.command(aliases=['s'])
    async def setting(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Open up the setting menu for the specified log channel."""
        channel = ctx.channel if not channel else channel

        data = self.find(ctx.guild.id, channel.id)

        if isinstance(data, Notify):
            if channel.id in self.instance:
                return await ctx.reply(f"There is a instance of setting menu for {channel.mention} already, "
                                       "try again later.")

            self.instance.append(channel.id)

            message = await ctx.reply("Processing . . .")
            ret = "First"
            while ret in ["First", "Continue"]:
                ret = await self.setting_menu(channel, message, data, ctx.author, ret == "Continue")
            if ret != "Deleted" or not ret:
                temp = data.data
                self.db.update_one(
                    {"guild_id": ctx.guild.id, "_id": channel.id},
                    {"$set": {"enter": temp['enter'], "leave": temp['leave'], "kick": temp['kick'], "ban": temp['ban'],
                              "unban": temp['unban'], "trigger": temp['trigger'], "raid": temp['raid'],
                              "member_update": temp['member_update'], "server_update": temp['server_update'],
                              "vc_update": temp['vc_update']}}
                )

            self.instance.remove(channel.id)
        else:
            await ctx.reply(f"**#{channel}** is not a log channel")

    async def setting_menu(self, channel: discord.TextChannel, message: discord.Message, data: Notify,
                           original_author: typing.Union[discord.User, discord.Member], emoted: bool = True):
        """
        Async method involved with modification of a log channel's settings.

        Parameters
        ----------
        channel : discord.TextChannel
            The log channel
        message : discord.Message
            The target setting menu message
        data : Notify
            pass in Notify class for modifications
        original_author : typing.Union[discord.User, discord.Member]
            the user that called the setting menu command
        emoted : bool
            whether or not the message contains the necessary emotes already. Default is true

        Returns
        -------
        str
            return of "Continue" will instruct the setting menu to continue and "Delete" specified no further action
        None
            indicates that all modifications needed are done.
        """
        y = "✅"
        n = "🛑"
        temp = f"=============================================\n" \
               f"➡|=> {y if data.data['enter'] else n} |=>User joining the server\n" \
               f"🚪|=> {y if data.data['leave'] else n} |=>User leaving the server\n" \
               f"👢|=> {y if data.data['kick'] else n} |=>User kicked from the server\n" \
               f"🔨|=> {y if data.data['ban'] else n} |=>User banned from the server\n" \
               f"👼|=> {y if data.data['unban'] else n} |=>User un-banned from the server\n" \
               f"⚠|=> {y if data.data['trigger'] else n} |=>Scanners within the server\n" \
               f"🚶|=> {y if data.data['raid'] else n} |=>Possible raid warning alert\n" \
               f"🔃|=> {y if data.data['member_update'] else n} |=>Display server member updates [name, nickname]\n" \
               f"🏗|=> {y if data.data['server_update'] else n} |=>Display server changes\n" \
               f"💬|=> {y if data.data['vc_update'] else n} |=>Display member joining, moving, leaving voice chat"
        embed = discord.Embed(
            colour=0xfdcb6e,
            title=f"Reaction to change what log will the bot send in this channel",
            description=temp
        )
        embed.set_author(name=f"{channel} log settings")
        embed.add_field(name="Freezing", value="reacting with '⏸' will freeze this menu, "
                                               "command redo will be needed.")
        embed.set_footer(text=f"react with '❌' to no longer make [{channel}] a log channel")

        await message.edit(embed=embed, content="")

        if not emoted:
            for i in self.reactions:
                await message.add_reaction(emoji=i)

        def check(reaction1: discord.Reaction, user1: discord.User):
            if (reaction1.message.id == message.id) and (user1.id == original_author.id):
                if str(reaction1.emoji) in self.reactions:
                    return True

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=check)
        except asyncio.TimeoutError:
            await message.edit(embed=None, content=f"**{channel}** setting menu timed out ⏱")
            await message.clear_reactions()
        else:
            if reaction.emoji == "⏸":
                await message.clear_reactions()
                embed.remove_field(0)
                embed.set_footer(text="Frozen")
                embed.title = None
                embed.timestamp = message.created_at
                await message.edit(embed=embed)
            elif reaction.emoji == "❌":

                def sure(reaction1, user1):
                    if (reaction1.message.id == message.id) and (user1.id == original_author.id):
                        if str(reaction1.emoji) in self.second:
                            return True

                await message.clear_reactions()
                await message.edit(content=f"You sure you want to turn off log messages for **{channel}**?",
                                   embed=None)
                await message.add_reaction(emoji="✔")
                await message.add_reaction(emoji="🇽")

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=sure)
                except asyncio.TimeoutError:
                    await message.edit(embed=None, content=f"un-log **{channel}** confirm menu timed out ⏱")
                    await message.clear_reactions()
                else:
                    if reaction.emoji == "🇽":
                        await message.delete()
                    if reaction.emoji == "✔":
                        self.db.delete_one({"guild_id": message.guild.id, "_id": channel.id})
                        await message.clear_reactions()
                        self.update(message.guild.id)
                        await message.edit(content=f"**{channel}** will no longer receive any log messages.")
                        return "Deleted"
            else:
                await message.remove_reaction(emoji=reaction.emoji, member=user)
                req = self.label[reaction.emoji]
                res = data.data[req]
                data.data[req] = False if res else True
                return "Continue"

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """
        Async method called when bot detects a server change. This will check for server changes and send info
        on the specific log channel.

        Parameters
        ----------
        before : discord.Guild
            Server information before the change
        after : discord.Guild
            Server information after the change
        """
        try:
            data = self.memory[after.id]
        except KeyError:
            return

        embed = discord.Embed(
            colour=0x3498db,
            timestamp=datetime.datetime.utcnow(),
            title="🔼 Server Updated 🔼"
        )

        def change(title, be, af):
            embed.add_field(name=f"{title}",
                            value=f"**from** {be} **to** {af}", inline=False)

        if before.name != after.name:
            change("Server Name Change", f"`{before.name}`", f"`{after.name}`")
        if before.owner != after.owner:
            change("Owner Change", before.owner.mention, after.owner.mention)
        if before.region != after.region:
            change("Region Change", f"`{before.region}`", f"`{after.region}`")
        if before.premium_tier != after.premium_tier:
            change("Server Boost Level Change", f"Level `{before.premium_tier}`",
                   f"`Level {after.premium_tier}`")
        if before.afk_channel != after.afk_channel:
            change("AFK Voice Channel Change", f"`{before.afk_channel}`", f"`{after.afk_channel}`")
        if before.afk_timeout != after.afk_timeout:
            change("AFK Time Out Change", f"`{before.afk_timeout / 60} minutes`",
                   f"`{after.afk_timeout / 60} minutes`")
        if before.default_notifications != after.default_notifications:
            change("Notification Level Change", f"`{before.default_notifications}`",
                   f"`{after.default_notifications}`")
        if before.verification_level != after.verification_level:
            change("Verification Level Change", f"`{before.verification_level}`",
                   f"`{after.verification_level}`")
        if before.explicit_content_filter != after.explicit_content_filter:
            change("Content Filter Change", f"`{before.explicit_content_filter}`",
                   f"`{after.explicit_content_filter}`")

        if embed.fields == discord.Embed.Empty or len(embed.fields) < 1:
            return

        for i in data:
            if i.data['server_update']:
                channel = self.bot.get_channel(i.channel)
                if not channel:
                    self.db.delete_one({"guild_id": i.guild, "_id": i.channel})
                    return

                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        """
        Async method called when bot detects a voice state update. This will detect and send info in embed form to
        the specific log channel.

        Parameters
        ----------
        member : discord.Member
            member that updated their voice state
        before : discord.VoiceState
            the voice state before
        after : discord.VoiceState
            voice state after
        """
        try:
            data = self.memory[member.guild.id]
        except KeyError:
            return

        now = datetime.datetime.utcnow()

        embed_stuff = {
            "🎤": (0x7bed9f, f"{member.mention} **joined** `{after.channel}`"),
            "🚪": (0xff6b81, f"{member.mention} **left** `{before.channel}`"),
            "🔄": (0xeccc68, f"{member.mention} **switched** from `{before.channel}` to `{after.channel}`"),
            "📺": (0x6c5ce7, f"{member.mention} is **Live** in `{after.channel}`!"),
            "⏹": (0x6c5ce7, f"{member.mention} is no longer live.")
        }

        if not before.channel:
            label = "🎤"
        elif not after.channel:
            label = "🚪"
        elif before.channel != after.channel:
            label = "🔄"
        elif after.self_stream and not before.self_stream:
            label = "📺"
        elif not after.self_stream and before.self_stream:
            label = "⏹"
        else:
            return

        embed = discord.Embed(colour=embed_stuff[label][0], timestamp=now, description=embed_stuff[label][1])
        embed.set_footer(icon_url=member.avatar_url_as(size=64), text=label)

        for i in data:
            if i.data['vc_update']:
                channel = self.bot.get_channel(i.channel)
                if not channel:
                    self.db.delete_one({"guild_id": i.guild, "_id": i.channel})
                    return

                if embed:
                    await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Async method to be called upon when bot detect a member joining the server and send the information to the
        appropriate log channel.

        Parameters
        ----------
        member : discord.Member
            new member who joined the server
        """
        try:
            await self.bot.get_cog("Scanner").scan_name(member.guild, member, True)
        except ValueError:
            pass

        try:
            data = self.memory[member.guild.id]
        except KeyError:
            return

        embed = discord.Embed(
            colour=0x55efc4,
            timestamp=member.joined_at,
            description=f"{member.mention} ➡ **{member.guild}**"
        )
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_author(name="New member!", icon_url=member.guild.icon_url)
        embed.add_field(name="User ID", value=member.id)
        embed.add_field(name="Account Birthday", value=member.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))
        temp = member.joined_at - member.created_at
        # code reference: https://stackoverflow.com/questions/28775345/python-strftime-clock
        seconds = temp.days * 86400 + temp.seconds
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        years, days = divmod(days, 365)
        temp = "{years:02d} years {days:02d} days {hours:02d} hours {minutes:02d} " \
               "minutes {seconds:02d} seconds".format(**vars())
        embed.add_field(name="Account Age", value=temp, inline=False)
        url = self.bot.user.avatar_url_as(size=64)
        if seconds <= 1:
            embed.set_footer(icon_url=url, text="Hi! You joining the server with a test account?")
        elif hours <= 1:
            embed.set_footer(icon_url=url, text="This account is rather new...")
        elif days <= 7:
            embed.set_footer(icon_url=url, text="New to discord yo!")

        for i in data:
            if i.data['enter']:
                channel = self.bot.get_channel(i.channel)
                if not channel:
                    self.db.delete_one({"guild_id": i.guild, "_id": i.channel})
                    return

                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """
        Async method to be called upon when bot detect a member leaving the server and send the information to the
        appropriate log channel. This method also checks whether or not the user was kicked.

        Parameters
        ----------
        member : discord.Member
            member who left the server
        """
        try:
            data = self.memory[member.guild.id]
        except KeyError:
            return

        time = datetime.datetime.utcnow()

        embed = discord.Embed(
            colour=0xe74c3c,
            timestamp=time,
            description=f"{member.mention} ⬅ **{member.guild}**"
        )
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_author(name="Someone left...", icon_url=member.guild.icon_url)
        embed.add_field(name="User ID", value=member.id)
        embed.add_field(name="Leave Time",
                        value=time.strftime("%#d %B %Y, %I:%M %p UTC"))

        kicked = None

        def check(e: discord.AuditLogEntry):
            return e.target.id == member.id and e.action == discord.AuditLogAction.kick

        entry = await member.guild.audit_logs(
            action=discord.AuditLogAction.kick, after=(datetime.datetime.utcnow() - datetime.timedelta(minutes=1))
        ).find(check)

        if entry:
            kicked = discord.Embed(
                colour=0xe74c3c,
                timestamp=entry.created_at,
                description=f"**{entry.target.name}** got drop kicked out of **{member.guild}**!"
            )
            kicked.set_thumbnail(url=member.avatar_url)
            kicked.set_author(name="👢 Booted!", icon_url=member.guild.icon_url)
            kicked.set_footer(text="Kicked")
            kicked.add_field(inline=False, name="Kicked by:", value=entry.user.mention)
            kicked.add_field(inline=False, name="Reason:", value=entry.reason)
            kicked.add_field(name="User ID", value=member.id)
            kicked.add_field(name="Kick Time", value=entry.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))

        for i in data:
            target = self.bot.get_channel(i.channel)
            if not target:
                self.db.delete_one({"guild_id": i.guild, "_id": i.channel})
                return

            if i.data['leave']:
                await target.send(embed=embed)

            if i.data['kick'] and kicked:
                await target.send(embed=kicked)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: typing.Union[discord.Member, discord.User]):
        """
        Async method to be called upon when bot detect a member is banned the server and send the information to the
        appropriate log channel.

        Parameters
        ----------
        guild : discord.Guild
            server that initialized the ban
        user : typing.Union[discord.Member, discord.User]
            The user/member banned
        """
        try:
            data = self.memory[guild.id]
        except KeyError:
            return

        # wait for entry to be logged
        def check(e: discord.AuditLogEntry):
            return e.target.id == user.id and e.action == discord.AuditLogAction.ban

        entry = await guild.audit_logs(
            action=discord.AuditLogAction.ban, limit=5
        ).find(check)

        embed = discord.Embed(
            timestamp=datetime.datetime.utcnow() if not entry else entry.created_at,
            colour=0xED4C67,
            description=f"**{user.name}** got hit by a massive hammer and vanished into the "
                        f"shadow realm!"
        )
        embed.set_footer(text="Banned")
        embed.set_thumbnail(url=user.avatar_url)
        embed.set_author(name="🔨 Banned!", icon_url=guild.icon_url)
        embed.add_field(name="User ID", value=user.id)

        if entry:
            embed.add_field(inline=False, name="Banned by:", value=entry.user)
            embed.add_field(inline=False, name="Reason:", value=entry.reason)
            embed.add_field(name="Ban Time", value=entry.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))
        else:
            embed.add_field(inline=False, name="404 Not Found", value="Failed to fetch ban data from audit log")

        for i in data:
            if i.data['ban'] and embed:
                channel = self.bot.get_channel(i.channel)
                if not channel:
                    self.db.delete_one({"guild_id": i.guild, "_id": i.channel})
                else:
                    if embed:
                        await self.bot.get_channel(i.channel).send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """
        Async method to be called upon when bot detect a member being unbanned from the server and send the information
        to the appropriate log channel.

        Parameters
        ----------
        guild : discord.Guild
            server initialized the unban
        user : discord.User
            user being unbanned
        """
        try:
            data = self.memory[guild.id]
        except KeyError:
            return

        embed = None

        async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=3):
            if entry.target.id == user.id:
                embed = discord.Embed(
                    colour=0x1abc9c,
                    timestamp=entry.created_at,
                    description=f"Don't lose hope just yet **{user.name}**! Stay determined!"
                )
                embed.set_footer(text="Unbanned")
                embed.set_thumbnail(url=user.avatar_url)
                embed.set_author(name="✝ Unbanned!", icon_url=guild.icon_url)
                embed.add_field(inline=False, name="Unbanned by:", value=entry.user.mention)
                embed.add_field(inline=False, name="Reason:", value=entry.reason)
                embed.add_field(name="User ID", value=user.id)
                embed.add_field(name="Unban Time", value=entry.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))
                break

        for i in data:
            if i.data['unban']:
                channel = self.bot.get_channel(i.channel)
                if not channel:
                    self.db.delete_one({"_id": i.channel})
                else:
                    if embed:
                        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Async method / listener to be called when bot detects any member update. This method will attempt to relay
        the new nickname compared to the old one

        Parameters
        ----------
        before: discord.Member
            member reference before the update
        after: discord.Member
            member reference after
        """
        if before.nick == after.nick:
            return
        try:
            result = await self.bot.get_cog("Scanner").scan_name(after.guild, after, special=after.nick is None)
        except ValueError:
            result = False

        if not result:
            try:
                data = self.memory[after.guild.id]
            except KeyError:
                return

            embed = discord.Embed(
                timestamp=datetime.datetime.utcnow(),
                colour=0x9980FA,
                description=after.mention
            )
            embed.set_author(name="✍ Nickname change!", icon_url=after.avatar_url)
            if before.nick:
                embed.add_field(name="Before", value=before.nick, inline=False)
            if after.nick:
                embed.add_field(name="Now", value=after.nick, inline=False)

            for i in data:
                if i.data['member_update']:
                    channel = self.bot.get_channel(i.channel)
                    if not channel:
                        self.db.delete_one({"_id": i.channel})
                    else:
                        if embed:
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """
        Async method / listener to be called when bot detects any user update. This method will attempt to relay
        the new username compared to the old one for server the user is in and has setup logging channels

        Parameters
        ----------
        before: discord.User
            user before the update
        after: discord.User
            user after the update
        """
        if (before.name == after.name) and (before.discriminator == after.discriminator):
            return

        is_in = []
        for i in self.bot.guilds:
            if i.get_member(after.id):
                is_in.append(i)

        for i in is_in:
            try:
                if before.name == after.name:
                    raise ValueError
                result = await self.bot.get_cog("Scanner").scan_name(i, after)
            except ValueError:
                result = False

            if not result:
                try:
                    data = self.memory[i.id]
                except KeyError:
                    return

                embed = discord.Embed(
                    colour=0x45aaf2,
                    timestamp=datetime.datetime.utcnow(),
                    description=after.mention
                )
                embed.set_author(name="✍ Username change!", icon_url=after.avatar_url)
                embed.add_field(name="Before", value=before.display_name, inline=False)
                embed.add_field(name="Now", value=after.display_name, inline=False)

                for k in data:
                    if k.data['member_update']:
                        channel = self.bot.get_channel(k.channel)
                        if not channel:
                            self.db.delete_one({"_id": k.channel})
                        else:
                            if embed:
                                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """
        Async method to be called when bot detects a text channel deletion

        Parameters
        ----------
        channel: discord.abc.GuildChannel
            the channel being deleted from a server
        """
        if isinstance(channel, discord.TextChannel):
            data = self.find(channel.guild.id, channel.id)
            if data:
                self.db.delete_one({"_id": channel.id})
                self.update(channel.guild.id)
