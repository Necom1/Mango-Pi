import typing
import discord
import asyncio
import datetime
from discord.ext import commands
from Components.MangoPi import MangoPi
from Components.Detector import Detector
from Components.DelayedTask import range_calculator


async def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog
    """
    await bot.add_cog(Scanner(bot))
    print("Load Cog:\tScanner")


async def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog
    """
    await bot.remove_cog("Scanner")
    print("Unload Cog:\tScanner")


class Scanner(commands.Cog):
    """
    Class Scanner inherited from commands.Cog containing scanner commands

    Attributes
    ----------
    bot: MangoPi
        bot reference
    data: dict
        dictionary containing all the Detector classes
    s_db: MongoClient
        mongo collection "scanner" reference
    verify: list
        list containing the check and x mark emotes
    options: list
        list containing the emote reaction for Scanner setting menu
    ports: list
        list containing the emote reaction for include or exclude menu
    default: str
        the default user name/nickname to change to
    """

    def __init__(self, bot: MangoPi):
        """
        Constructor for Cog Scanner

        Parameters
        ----------
        bot: MangoPi
            pass in bot reference
        """
        self.bot = bot
        self.data = {}
        self.names = {}
        self.s_db = bot.mongo["scanner"]
        self.n_db = bot.mongo["name_change"]
        self.verify = ["✅", "❌"]
        self.options = ['💡', '🗑', '👮', '💥', '⏸']
        self.ports = ['📝', '👥', '💬', '📛', '🚫']
        self.default = "Mango 🥭"
        self.update()

    def update(self, guild: int = None):
        """
        Method to populate or update data base on data from mongoDB

        Parameters
        ----------
        guild: int
            the specific server to update, if not then update everything
        """
        if not guild:
            self.data.clear()
            self.names.clear()
            data = self.s_db.find({})
            names = self.n_db.find({})
            for i in names:
                self.names.update({i["_id"]: i["name"]})
        else:
            try:
                self.data[guild].clear()
            except KeyError:
                self.data.update({guild: {}})
                
            data = self.s_db.find({"guild": guild})
            name = self.n_db.find_one({"_id": guild})

            if name:
                try:
                    self.names[guild] = name["name"]
                except KeyError:
                    self.names.update({guild: name["name"]})

        for i in data:
            try:
                self.data[i["guild"]].update({i["name"]: Detector(i)})
            except KeyError:
                self.data.update({i["guild"]: {i["name"]: Detector(i)}})

    def find(self, guild: int, name: str):
        """
        Method that attempts to return  the Detector within self.data

        Parameters
        ----------
        guild: int
            server ID for the Detector
        name: str
            name of the Detector

        Returns
        -------
        Detector
            return the specified Detector class if found
        """
        try:
            return self.data[guild][name]
        except KeyError:
            return

    async def scan_name(self, guild: discord.Guild, after: typing.Union[discord.Member, discord.User],
                        new_member: bool = False, special: bool = False):
        """
        Async method that scans either the username or the nickname base on the passed in type of after parameter, and
        send warning message if anything bad detected.

        Parameters
        ----------
        guild: discord.Guild
            the guild reference for the passed in user or member
        after: typing.Union[discord.Member, discord.User]
            nickname or username to scan
        new_member: bool
            whether or not "after" is a new member
        special: bool
            on the assumption that "after" is a member reference, however, scan username instead of nickname

        Returns
        -------
        bool
            Whether or not any "normal" notification should be sent regarding the user/member update
        """
        scan_nick = isinstance(after, discord.Member) and not special
        if scan_nick:
            try:
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                    if entry.user.id == self.bot.user.id:
                        return True
                    if entry.user.id != entry.target.id and after.id == entry.target.id:
                        return False
            except discord.errors.Forbidden:
                return False
        else:
            after = guild.get_member(after.id) if isinstance(after, discord.User) else after
            if not after:
                return False

        try:
            data = self.data[guild.id]
        except KeyError:
            return False

        result = {}
        rename = False
        warn = []
        now = datetime.datetime.utcnow()

        for k, v in data.items():
            temp = v.scan(after.nick if scan_nick and not new_member else after.name, after)
            if temp:
                result[k] = temp
                rename = v.delete or rename
                if v.warn:
                    for i in temp:
                        if i not in warn:
                            warn.append(i)

        if len(result) < 1:
            return False

        if rename:
            try:
                new = self.names[guild.id]
            except KeyError:
                new = self.default
            if new_member:
                reason = "Bad username on join"
            elif scan_nick:
                reason = "Illegal Nickname"
            else:
                reason = "Illegal Username"
            try:
                await after.edit(nick=new, reason=reason)
            except discord.errors.Forbidden:
                return False

        if len(warn) > 0:
            reason = ", ".join(warn)

            if new_member:
                reason = f"Username contained banned words: `{reason}` on Join"
            elif scan_nick:
                embed = discord.Embed(
                    timestamp=now,
                    description=f"Having **{reason}** in your nickname isn't allowed here.",
                    colour=0xf1c40f
                ).set_footer(icon_url=str(after.avatar.replace(size=64).url)).set_author(icon_url=guild.icon.replace(size=64).url, 
                                                                                         name=f"{guild.name}")
                try:
                    await after.send("⚠ Auto Warn ⚠", embed=embed)
                except discord.HTTPException:
                    pass
                reason = f"Nickname contained banned words: {reason}"
            else:
                reason = f"Username contained banned words: {reason}"
            try:
                self.bot.get_cog("Warn").add_warn(now, guild.id, after.id,
                                                  self.bot.user.id, 1, reason)
            except ValueError:
                pass

        string = ""
        for k, v in result.items():
            temp = ', '.join(v)
            string += f"**__{k}__**:\n{temp}\n\n"
        try:
            channels = self.bot.get_cog("Logging").memory[guild.id]
        except (KeyError, ValueError):
            channels = []
        if new_member:
            embed = discord.Embed(
                colour=0xF79F1F,
                timestamp=datetime.datetime.utcnow(),
                description=after.mention
            )
            embed.set_author(icon_url=after.avatar.replace(size=64).url, name="🚨 Bad Name on Join ⚠")
        elif scan_nick:
            embed = discord.Embed(
                colour=0xF79F1F,
                timestamp=now,
                description=after.mention
            )
            embed.set_author(icon_url=after.avatar.replace(size=64).url, name="🚨 Bad Nickname!")
        else:
            if special:
                return True
            embed = discord.Embed(
                colour=0xF79F1F,
                timestamp=now,
                description=after.mention
            )
            embed.set_author(icon_url=after.avatar.replace(size=64).url, name="🚨 Bad Username!")
        embed.add_field(inline=False, name="Problematic Words", value=string)
        for i in channels:
            if i.data['trigger']:
                channel = self.bot.get_channel(i.channel)
                if channel:
                    await channel.send(embed=embed)

        return True

    @commands.group(aliases=["s"])
    @commands.has_permissions(manage_channels=True)
    async def scanner(self, ctx: commands.Context):
        """Scanner group commands, invoke this with additional sub-command will bring up scanner help menu."""
        if not ctx.invoked_subcommand:
            pre = ctx.prefix

            embed = discord.Embed(
                title="`Scanner` Commands",
                colour=0xff6b6b
            )
            embed.add_field(inline=False, name=f"{pre}s c <name>",
                            value="Create a new scanner menu.")
            embed.add_field(inline=False, name=f"{pre}s s <scanner name>",
                            value="Open up the setting menu with option to turn on or off the mentioned scanner, "
                                  "delete scanner, toggle auto delete, or toggle auto-warn.")
            embed.add_field(inline=False, name=f"{pre}s + <scanner name> <word/phrase>",
                            value="Add the word/phrase into that specified scanner.")
            embed.add_field(inline=False, name=f"{pre}s - <scanner name> <existing word/phrase>",
                            value="Remove the word/phrase from the specified scanner.")
            embed.add_field(inline=False, name=f"{pre}s ++ <'words to add'>...",
                            value="Add multiple words into the specified scanner separated by space.")
            embed.add_field(inline=False, name=f"{pre}s -- <'words to remove'>...",
                            value="Remove multiple words into the specified scanner separated by space.")
            embed.add_field(inline=False, name=f"{pre}s l (scanner name) (page number)",
                            value="List all the scanners in the server no name mentioned, else will list word "
                                  "list of that scanner.")
            embed.add_field(inline=False, name=f"{pre}s i <scanner name> <channel mention or user mention or "
                                               f"role mention or ID>",
                            value="Add or remove the specified item into/from the ignore list")
            embed.add_field(inline=False, name=f"{pre}s il (page number)",
                            value="Display the ignored users, channels, and roles for this scanners")
            embed.add_field(inline=False, name=f"{pre}s include <scanner for import> <scanner to import data from>",
                            value="Import selectable data from one scanner to another")
            embed.add_field(inline=False, name=f"{pre}s exclude <scanner for modification> <scanner data reference>",
                            value="Delete selectable data from target scanner based on the specified scanner")
            embed.add_field(inline=False, name=f"{pre}s name",
                            value="Display the nickname to place on the user triggering the scanner")
            embed.add_field(inline=False, name=f"{pre}s change (new nickname)",
                            value="Change the nickname to change on scanner trigger")

            await ctx.reply(embed=embed)

    @scanner.command(aliases=["c"])
    async def create(self, ctx: commands.Context, *, name: str):
        """Create a new scanner with the specified name."""
        data = self.find(ctx.guild.id, name)
        if len(name) > 51:
            return await ctx.reply("Scanner name is too long, try keep it under or equal to 50 characters.")
        if data:
            return await ctx.reply("Scanner with the same name already exist")
        else:
            self.s_db.insert_one({"guild": ctx.guild.id, "name": name, "delete": True, "warn": False, "active": False,
                                  "words": [], "channels": [], "users": [], "roles": []})
            self.update(ctx.guild.id)
            await ctx.message.add_reaction(emoji="👍")

    @scanner.command(aliases=["s"])
    async def setting(self, ctx: commands.Context, *, name: str):
        """Open scanner setting menu."""
        data = self.find(ctx.guild.id, name)
        if not data:
            return await ctx.reply("Can not find the specified scanner")

        embed = discord.Embed(
            colour=0x55efc4 if data.active else 0xff6b81,
            title=f"Settings for `{name}` - " + ("Active" if data.active else "Inactive"),
            timestamp=ctx.message.created_at
        )
        embed.add_field(name="Auto Delete/Change", value=data.delete)
        embed.add_field(name="Auto Warn", value=data.warn)
        embed.add_field(name="Word Count", value=f"{len(data.words)}", inline=False)
        embed.add_field(name="Ignored User Count", value=f"{len(data.users)}", inline=False)
        embed.add_field(name="Ignored Roles Count", value=f"{len(data.roles)}", inline=False)
        embed.add_field(name="Ignored Channel Count", value=f"{len(data.channels)}", inline=False)
        embed.add_field(name="Options", inline=False,
                        value="💡 - Toggle on/off scanner\n🗑 - Toggle on/off auto-delete\n"
                              "👮 - Toggle on/off auto warn\n💥 - Delete the scanner\n⏸ - Freeze the setting menu")
        message = await ctx.reply(embed=embed)
        for i in self.options:
            await message.add_reaction(emoji=i)

        def check(reaction1: discord.Reaction, user1: discord.User):
            if (reaction1.message.id == message.id) and (user1.id == ctx.author.id):
                if str(reaction1.emoji) in self.options:
                    return True

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)
        except asyncio.TimeoutError:
            await message.edit(embed=None, content="Scanner setting menu timed out ⌛")
            return await message.clear_reactions()

        if reaction.emoji == '💡':
            data.active = not data.active
            self.s_db.update_one({"guild": ctx.guild.id, "name": name}, {"$set": {"active": data.active}})
            await message.edit(embed=None,
                               content=f"word list `{name}` is now " + ("active" if data.active else "inactive"))
        elif reaction.emoji == '🗑':
            data.delete = not data.delete
            self.s_db.update_one({"guild": ctx.guild.id, "name": name}, {"$set": {"delete": data.delete}})
            await message.edit(embed=None,
                               content=f"auto deletion for `{name}` is now " + ("on" if data.delete else "off"))
        elif reaction.emoji == '👮':
            data.warn = not data.warn
            self.s_db.update_one({"guild": ctx.guild.id, "name": name}, {"$set": {"warn": data.warn}})
            await message.edit(embed=None, content=f"auto warn for `{name}` is now " + ("on" if data.delete else "off"))
        elif reaction.emoji == '⏸':
            embed.remove_field(6)
            embed.set_footer(text="Setting menu paused", icon_url=self.bot.user.avatar.replace(size=64).url)
            await message.clear_reactions()
            return await message.edit(embed=embed)
        else:
            def check(reaction1: discord.Reaction, user1: discord.User):
                if (reaction1.message.id == message.id) and (user1.id == ctx.author.id):
                    if reaction1.emoji in self.verify:
                        return True

            await message.clear_reactions()
            await message.edit(embed=None, content=f"You sure you want to delete scanner `{name}`?")
            for i in self.verify:
                await message.add_reaction(emoji=i)

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)
            except asyncio.TimeoutError:
                await message.edit(content="scanner deletion confirmation menu timed out ⌛")
            else:
                if reaction.emoji == "❌":
                    await message.clear_reactions()
                    return await message.edit(content="Action cancelled")
                else:
                    self.s_db.delete_one({"guild": ctx.guild.id, "name": name})
                    await message.edit(content=f"Scanner `{name}` deleted")
            self.update(ctx.guild.id)

        await message.clear_reactions()

    @scanner.command(aliases=["+"])
    async def add(self, ctx: commands.Context, name: str, *, word: str):
        """Add the specified phrase or word into the scanner"""
        data = self.find(ctx.guild.id, name)
        if not data:
            return await ctx.reply("Can not find the specified Scanner")

        word = word.lower()
        if word in data:
            return await ctx.reply(f"**{word}** is already inside the Scanner")

        data.words.append(word)
        data.words.sort()
        self.s_db.update_one({"guild": ctx.guild.id, "name": name}, {"$push": {"words": word}})
        await ctx.reply(f"**{word}** has been added into scanner `{name}`")

    @scanner.command(aliases=["-"])
    async def remove(self, ctx: commands.Context, name: str, *, word: str):
        """Attempt to remove the specified word from the scanner."""
        data = self.find(ctx.guild.id, name)
        if not data:
            return await ctx.reply("Can not find the specified scanner")

        word = word.lower()
        if word not in data:
            return await ctx.reply(f"**{word}** can not be found in the `{name}` Scanner")

        data.words.remove(word)
        self.s_db.update_one({"guild": ctx.guild.id, "name": name}, {"$pull": {"words": word}})
        await ctx.reply(f"**{word}** has been removed from `{name}`")

    @scanner.command(aliases=["++"])
    async def multiple_add(self, ctx: commands.Context, name: str, *words: str):
        """Add multiple words separated by space into the specified scanner. Put quotation mark around phrases."""
        data = self.find(ctx.guild.id, name)

        if len(words) < 1:
            return await ctx.reply("Please specified the words or phrases to add into the scanner")
        if not data:
            return await ctx.reply("Can not find the specified scanner")

        success = []
        fail = []

        for i in words:
            if i in data:
                fail.append(i)
            else:
                data.words.append(i)
                success.append(i)

        data.words.sort()

        if len(success) > 0:
            self.s_db.update_one({"guild": ctx.guild.id, "name": name}, {"$set": {"words": data.words}})

        reply = discord.Embed(
            title="Scanner multi-add result",
            colour=0x0097e6
        )
        if len(success) > 0:
            temp = ", ".join(success)
            reply.add_field(inline=False, name="Successfully added",
                            value=f"**{len(success)}** words into the scanner:\n\n{temp}")
        if len(fail) > 0:
            temp = ", ".join(fail)
            reply.add_field(inline=False, name="Failed to add",
                            value=f"**{len(fail)}** words as they already within that scanner:\n\n{temp}")

        if reply.fields is not discord.Embed.Empty:
            await ctx.reply(embed=reply)

    @scanner.command(aliases=["--"])
    async def multiple_remove(self, ctx: commands.Context, name: str, *words: str):
        """Remove multiple words separated by space from the specified scanner. Put quotation mark around phrases."""
        data = self.find(ctx.guild.id, name)

        if len(words) < 1:
            return await ctx.reply("Please specified the words or phrases to add into the scanner")
        if not data:
            return await ctx.reply("Can not find the specified scanner")

        success = []
        fail = []

        for i in words:
            if i in data:
                data.words.remove(i)
                success.append(i)
            else:
                fail.append(i)

        if len(success) > 0:
            self.s_db.update_one({"guild": ctx.guild.id, "name": name}, {"$set": {"words": data.words}})

        reply = discord.Embed(
            title="Scanner multi-remove result",
            colour=0xe67e22
        )
        if len(success) > 0:
            temp = ", ".join(success)
            reply.add_field(inline=False, name="Successfully removed",
                            value=f"**{len(success)}** words from the scanner:\n\n{temp}")
        if len(fail) > 0:
            temp = ", ".join(fail)
            reply.add_field(inline=False, name="Failed to remove",
                            value=f"**{len(fail)}** words as they can't be found within that scanner:\n\n{temp}")

        if reply.fields is not discord.Embed.Empty:
            await ctx.reply(embed=reply)

    @scanner.command(aliases=["l"])
    async def list(self, ctx: commands.Context, name: str = None, page: int = 1):
        """List the number of scanners within the server or display word list of a scanner with specific pages"""
        if not name:
            try:
                array = self.data[ctx.guild.id]
            except KeyError:
                return await ctx.reply("No scanner founded within this server")
            if len(array) < 1:
                return await ctx.reply("No scanner founded within this server")
            total = ""
            for i in array.values():
                temp = ""
                temp += "✅" if i.active else "❌"
                temp += "🗑" if i.delete else "📖"
                temp += "👮" if i.warn else "😴"
                total += f"{temp} **{i.name}**\n"
            await ctx.reply(embed=discord.Embed(
                title="Server Scanners",
                description=total,
                colour=0x81ecec
            ))
        else:
            if page < 1:
                return await ctx.reply("Page can't be less than 1")
            data = self.find(ctx.guild.id, name)
            if not data:
                return await ctx.reply("Can not find the specified scanner")

            info = ""
            start, end, total = range_calculator(30, len(data.words), page)

            if len(data.words) < 1:
                info = "Empty"
            else:
                for i in range(start, end):
                    info += f"{i + 1}. \t{data.words[i]}\n"

            embed = discord.Embed(
                title=f"Words in __{name}__ scanner",
                timestamp=ctx.message.created_at,
                colour=0xffdd59,
                description=info
            )

            if len(data.words) > 0:
                embed.set_footer(text=f"Page {page} / {total}")

            await ctx.reply(embed=embed)

    @scanner.command(aliases=["i"])
    async def ignore(self, ctx: commands.Context, name: str,
                     *targets: typing.Union[discord.Member, discord.TextChannel, discord.Role, int]):
        """Ignore/un-ignore the specified targets be it either IDs, channel, member, or role mention"""
        if len(targets) < 1:
            return await ctx.reply("Please specify the targets to ignore")

        data = self.find(ctx.guild.id, name)
        if not data:
            return await ctx.reply("Can not find the specified scanner")

        ignore = []
        undo = []
        error = []

        for i in targets:
            if isinstance(i, int):
                undo.append(i)
                if i in data.channels:
                    data.channels.remove(i)
                elif i in data.roles:
                    data.roles.remove(i)
                elif i in data.users:
                    data.users.remove(i)
                else:
                    undo.remove(i)
                    error.append(f"Failed to recognize ID: {i}")
            else:
                if i not in data:
                    if isinstance(i, discord.Member):
                        data.users.append(i.id)
                    elif isinstance(i, discord.TextChannel):
                        data.channels.append(i.id)
                    else:
                        data.roles.append(i.id)
                    ignore.append(i.mention)
                else:
                    if isinstance(i, discord.Member):
                        data.users.remove(i.id)
                    elif isinstance(i, discord.TextChannel):
                        data.channels.remove(i.id)
                    else:
                        data.roles.remove(i.id)
                    undo.append(i.mention)

        embed = discord.Embed(
            colour=0xc7ecee,
            title=f"Update Scanner __{name}__ ignore list result",
            timestamp=ctx.message.created_at
        )

        update = False

        if len(ignore) > 0:
            embed.add_field(inline=False, name=f"Successfully added **{len(ignore)}** items to the ignore list",
                            value="\n".join(ignore))
            update = True
        if len(undo) > 0:
            embed.add_field(inline=False, name=f"Successfully removed **{len(undo)}** items from the ignore list",
                            value="\n".join(undo))
            update = True
        if len(error) > 0:
            embed.add_field(inline=False, name="Failed to add the following undefined ID", value="\n".join(error))

        if update:
            self.s_db.update_one({"guild": ctx.guild.id, "name": name},
                                 {"$set": {"roles": data.roles, "channels": data.channels, "users": data.users}})
        await ctx.reply(embed=embed)

    @scanner.command(aliases=["il"])
    async def ignore_list(self, ctx: commands.Context, name: str, page: int = 1):
        """List all the ignore information within the scanner"""
        if page < 1:
            return await ctx.reply("Pages can't be less than 1")

        data = self.find(ctx.guild.id, name)
        if not data:
            return await ctx.reply("Can not find the specified scanner")

        embed = discord.Embed(
            timestamp=ctx.message.created_at,
            colour=0x575fcf,
            title=f"Scanner __{name}__ ignore list"
        )

        def embedding(kind: str, ins: list, e: discord.Embed):
            array = []
            for i in ins:
                if kind == "Users":
                    temp = ctx.guild.get_member(i)
                elif kind == "Roles":
                    temp = ctx.guild.get_role(i)
                else:
                    temp = ctx.guild.get_channel(i)
                if temp:
                    array.append(temp.mention)
                else:
                    err.append(f"{i} -\t{kind}")
            e.add_field(name=f"**{len(ins)}** {kind}", value="\n".join(array))

        if len(data.users) + len(data.channels) + len(data.roles) == 0:
            embed.description = "Empty"
        else:
            err = []
            if len(data.users) > 0:
                embedding("Users", data.users, embed)
            if len(data.roles) > 0:
                embedding("Roles", data.roles, embed)
            if len(data.channels) > 0:
                embedding("Channels", data.channels, embed)
            if len(err) > 0:
                embed.add_field(inline=False, name="Errors", value="\n".join(err))
        await ctx.reply(embed=embed)

    async def port_menu(self, ctx: commands.Context, title: str, modify: Detector, reference: Detector):
        """
        Static method that returns embed menu for include or exclude

        Parameters
        ----------
        ctx: commands.Context
            pass in context for reply message
        title: str
            title for the embed
        modify: Detector
            the modify Detector for analysis
        reference: Detector
            the reference dDetector for analysis

        Returns
        -------
        discord.Message, Detector, Detector, str
            the discord message bot replied, detector modify target data reference, detector reference data, the
            selected mode base on user reaction
        """
        embed = discord.Embed(
            title=title,
            colour=0x78e08f,
            description="📝 - Word List\n👥 - Users\n💬 - Channels\n📛 - Roles"
        )
        message = await ctx.reply(embed=embed)
        for i in self.ports:
            await message.add_reaction(emoji=i)

        def check(reaction1: discord.Reaction, user1: discord.User):
            return str(reaction1.emoji) in self.ports and user1.id == ctx.message.author.id \
                   and reaction1.message.id == message.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30, check=check)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            return await message.edit(embed=None, content="Menu timed out")

        await message.clear_reactions()

        if reaction.emoji == '🚫':
            return await message.edit(embed=None, content="Action cancelled")

        if reaction.emoji == '📝':
            modify = modify.words
            reference = reference.words
            mode = "Word List"
        elif reaction.emoji == '👥':
            modify = modify.users
            reference = reference.users
            mode = "Ignored Users"
        elif reaction.emoji == '💬':
            modify = modify.channels
            reference = reference.channels
            mode = "Ignored Channels"
        else:
            modify = modify.roles
            reference = reference.roles
            mode = "Ignored Roles"

        return message, modify, reference, mode

    @scanner.command()
    async def include(self, ctx: commands.Context, target: str, subject: str):
        """Attempt to add data from the subject scanner into the target scanner"""
        modify = self.find(ctx.guild.id, target)
        reference = self.find(ctx.guild.id, subject)
        if not modify:
            return await ctx.reply("Can not find the Scanner to modify")
        if not reference:
            return await ctx.reply("Can not find the reference Scanner")

        try:
            message, modified, reference, mode = await \
                self.port_menu(ctx, f"Which data to import from __{subject}__ to **__{target}__**?", modify, reference)
        except TypeError:
            return

        success = 0
        fail = 0

        for i in reference:
            if i not in modified:
                modified.append(i)
                success += 1
            else:
                fail += 1

        if success != 0:
            self.s_db.update_one({"guild": ctx.guild.id, "name": target},
                                 {"$set": {"users": modify.users, "channels": modify.channels, "roles": modify.roles,
                                           "words": modify.words}})

        embed = discord.Embed(
            colour=0x16a085,
            title=f"Result of importing {mode} data from __{subject}__ into **{target}**",
            description=f"Successfully added {success} items\nFailed to add {fail} items"
        )
        await message.edit(embed=embed)

    @scanner.command()
    async def exclude(self, ctx: commands.Context, target: str, subject: str):
        """Attempt to remove data based on the subject scanner from the target scanner"""
        modify = self.find(ctx.guild.id, target)
        reference = self.find(ctx.guild.id, subject)
        if not modify:
            return await ctx.reply("Can not find the Scanner to modify")
        if not reference:
            return await ctx.reply("Can not find the reference Scanner")

        try:
            message, modified, reference, mode = await \
                self.port_menu(ctx, f"Which data to remove based on __{subject}__ from **__{target}__**?",
                               modify, reference)
        except TypeError:
            return

        success = 0
        fail = 0

        for i in reference:
            if i in modified:
                modified.remove(i)
                success += 1
            else:
                fail += 1

        if success != 0:
            self.s_db.update_one({"guild": ctx.guild.id, "name": target},
                                 {"$set": {"users": modify.users, "channels": modify.channels, "roles": modify.roles,
                                           "words": modify.words}})

        embed = discord.Embed(
            colour=0xa29bfe,
            title=f"Result of removing {mode} data from __{subject}__ based on **{target}**",
            description=f"Successfully removed {success} items\nFailed to remove {fail} items"
        )
        await message.edit(embed=embed)

    @scanner.command()
    async def name(self, ctx: commands.Context):
        """Display the nickname to place on the user triggering the scanner"""
        try:
            data = self.names[ctx.guild.id]
        except KeyError:
            data = self.default
        await ctx.reply(data)

    @scanner.command()
    async def change(self, ctx: commands.Context, *, nickname: str = None):
        """Change the nickname to change on scanner trigger"""
        try:
            data = self.names[ctx.guild.id]
        except KeyError:
            if nickname == self.default:
                return await ctx.reply("Nothing has changed")
            self.n_db.insert_one({"_id": ctx.guild.id, "name": nickname})
            self.names.update({ctx.guild.id: nickname})
        else:
            if data == nickname:
                return await ctx.reply("Nothing has changed")
            data = nickname
            self.n_db.update({"_id": ctx.guild.id}, {"$set": {"name": data}})
        await ctx.message.add_reaction(emoji="👍")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Async method/event listener that scans the received new message from TextChannel through scanners and send
        notification to the appropriate channel if applicable

        Parameters
        ----------
        message: discord.Message
            the newly received message
        """
        if message.author.bot or message.channel.type != discord.ChannelType.text or message.content == "":
            return

        try:
            data = self.data[message.guild.id]
        except KeyError:
            return

        result = {}
        delete = False
        warn = []

        for k, v in data.items():
            temp = v.scan(message, message.author)
            if temp:
                result[k] = temp
                delete = v.delete or delete
                if v.warn:
                    for i in temp:
                        if i not in warn:
                            warn.append(i)

        if len(result) < 1:
            return

        try:
            location = self.bot.get_cog("Logging").memory[message.guild.id]
        except (ValueError, KeyError):
            location = []

        time = message.created_at
        mention = message.author.mention

        if delete:
            await message.delete()
            if len(warn) > 0:
                jump = await message.channel.send(f"Watch your language {message.author.mention}")
                jump = jump.jump_url
            else:
                jump = message.jump_url
        else:
            jump = message.jump_url

        if len(warn) > 0:
            reason = ', '.join(warn)
            try:
                self.bot.get_cog("Warn").add_warn(time, message.guild.id, message.author.id,
                                                  self.bot.user.id, 1, f"Used banned words: {reason}")
            except ValueError:
                pass

            try:
                await message.author.send("⚠ Auto warn ⚠", embed=discord.Embed(
                    timestamp=message.created_at,
                    description=f"Use of **{reason}** are banned. Go wash your hands.",
                    colour=0xf1c40f
                ).set_footer(icon_url=message.author.avatar.replace(size=64).url)
                                          .set_author(icon_url=message.guild.icon.replace(size=128).url,
                                                      name=f"{message.guild.name}"))
            except discord.HTTPException:
                pass

        if len(result) > 0:
            embed = discord.Embed(
                colour=0xe74c3c,
                timestamp=time,
                description=message.content,
                title=f"Message from **{message.author}** in **{message.channel}**"
            ).set_footer(icon_url=message.author.avatar.replace(size=64).url, text=f"User ID: {message.author.id}")
            embed.add_field(name="Time", value=message.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))
            embed.add_field(name="Message Location", value=f"[Jump]({jump})")
            embed.add_field(name="Mention", value=mention)
            string = ""
            for k, v in result.items():
                temp = ', '.join(v)
                string += f"**__{k}__**:\n{temp}\n\n"
            embed.add_field(inline=False, name="Problematic Words", value=string)
            if delete:
                embed.set_author(icon_url=message.guild.icon.replace(size=128).url, name="Automatic message deletion")

            for i in location:
                if i.data['trigger']:
                    channel = message.guild.get_channel(i.channel)
                    if channel:
                        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """
        Async method/event listener to be called when the bot detects a edit message update and send the edited
        through scanners

        Parameters
        ----------
        before: discord.Message
            the message before edit
        after: discord.Message
            message after edit
        """
        if after.author.bot or after.channel.type != discord.ChannelType.text or after.content == "":
            return

        try:
            data = self.data[after.guild.id]
        except KeyError:
            return

        result = {}
        delete = False
        warn = []

        for k, v in data.items():
            temp = v.scan(after, after.author)
            if temp:
                result[k] = temp
                delete = v.delete or delete
                if v.warn:
                    for i in temp:
                        if i not in warn:
                            warn.append(i)

        if len(result) < 1:
            return

        try:
            location = self.bot.get_cog("Logging").memory[after.guild.id]
        except (ValueError, KeyError):
            location = []

        time = datetime.datetime.utcnow()
        mention = after.author.mention

        if delete:
            await after.delete()
            if len(warn) > 0:
                jump = await after.channel.send(f"Watch your language {after.author.mention} even in edited message")
                jump = jump.jump_url
            else:
                jump = after.jump_url
        else:
            jump = after.jump_url

        if len(warn) > 0:
            reason = ", ".join(warn)
            try:
                self.bot.get_cog("Warn").add_warn(time, after.guild.id, after.author.id, self.bot.user.id, 1,
                                                  f"Used banned words in edit message: {reason}")
            except ValueError:
                pass

            try:
                await after.author.send("⚠ Auto warn ⚠", embed=discord.Embed(
                    timestamp=time,
                    description=f"Use of **{reason}** are banned, even in edited messages.",
                    colour=0xf1c40f
                ).set_footer(icon_url=after.author.avatar.replace(size=64).url)
                                          .set_author(icon_url=after.guild.icon.replace(size=128).url,
                                                      name=f"{after.guild.name}"))
            except discord.HTTPException:
                pass

        if len(result) > 0:
            embed = discord.Embed(
                colour=0xe74c3c,
                timestamp=time,
                title=f"Message from **{after.author}** in **{after.channel}**"
            ).set_footer(icon_url=after.author.avatar.replace(size=64).url, text=f"User ID: {after.author.id}")
            embed.add_field(inline=False, name="Message Before:", value=before.content)
            embed.add_field(inline=False, name="Message Edited to:", value=after.content)
            embed.add_field(name="Time", value=after.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))
            embed.add_field(name="Message Location", value=f"[Jump]({jump})")
            embed.add_field(name="Mention", value=mention)
            string = ""
            for k, v in result.items():
                temp = ', '.join(v)
                string += f"**__{k}__**:\n{temp}\n\n"
            embed.add_field(inline=False, name="Problematic Words", value=string)
            if delete:
                embed.set_author(icon_url=after.guild.icon.replace(size=128).url, name="Automatic message deletion")

            for i in location:
                if i.data['trigger']:
                    channel = after.guild.get_channel(i.channel)
                    if channel:
                        await channel.send(embed=embed)
