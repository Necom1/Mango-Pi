import discord
import typing
import asyncio
from discord.ext import commands


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(RoleMenu(bot))
    print("Load Cog:\tRoleMenu")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("RoleMenu")
    print("Unload Cog:\tRoleMenu")


class RoleSelector:
    """
    Class RoleSelector that deals with reaction based role management system.

    Attributes
    ----------
    guild: discord.Guild
        the guild reference for the RoleSelector of that server
    name: str
        name of the RoleSelector (Role Menu)
    message: discord.Message
        the targeted message reference
    channel_id: int
        ID of the channel where the target message is located
    message_id: int
        ID of the message where the target message
    custom: list
        list 'custom' data from mongo
    raw: list
        list 'emote' data from mongo
    multiple: bool
        whether or not the system allows multiple roles within the system on a member
    active: bool
        on/off indicator for this RoleSelector
    emote_to_role: dict
        dictionary containing emote as key and role as
    error: dict
        dictionary of either role or emote error, with emote id or str as key and role_id as value
    """

    def __init__(self, bot: commands.Bot, pack: dict):
        """
        Constructor for RoleSelector class.

        Parameters
        ----------
        bot: commands.Bot
            pass in bot to fetch needed data
        pack: dict
            pass in the data from mongoDB to initialize the class

        Raises
        ------
        discord.DiscordException
            if bot can not find the discord server within cache
        """
        self.guild = bot.get_guild(pack["guild_id"])
        if not self.guild:
            raise discord.DiscordException("Can not find the given server for the RoleSelector")
        self.name = pack["name"]
        self.message = None
        self.channel_id = pack["channel_id"]
        self.message_id = pack["message_id"]
        self.custom = pack['custom']
        self.raw = pack['emote']
        self.multiple = pack["multi"]
        self.active = (self.channel_id and self.message_id) if pack["active"] else pack["active"]
        self.emote_to_role = {}
        self.error = {}
        for i in range(len(pack["custom"])):
            role = self.guild.get_role(pack["role_id"][i])
            emote = pack["emote"][i]
            if pack["custom"][i]:
                emote = bot.get_emoji(int(emote))
            if role and emote:
                self.emote_to_role.update({emote: role})
            else:
                self.error.update({pack["emote"][i]: pack["role_id"][i]})
        asyncio.get_event_loop().create_task(self.find_message(bot))

    async def find_message(self, bot: commands.Bot):
        """
        Async method the tries to find the target message from class data and append result to self.message

        Parameters
        ----------
        bot: commands.Bot
            pass in bot reference to find the target message
        """
        channel = self.guild.get_channel(self.channel_id)
        if channel:
            self.message = await channel.fetch_message(self.message_id)
            if self.message:
                await self.organize_reactions(bot.user.id)

    async def organize_reactions(self, safe: int):
        """
        Async method that reorganizes reaction within a target message

        Parameters
        ----------
        safe: int
            bot's ID
        """
        if not self.message or not self.active:
            return

        for reaction in self.message.reactions:
            try:
                role = self.emote_to_role[reaction.emoji]
            except KeyError:
                pass
            else:
                async for i in reaction.users():
                    if i.id != safe:
                        if isinstance(i, discord.User):
                            await reaction.remove(i)
                        else:
                            if role not in i.roles:
                                await reaction.remove(i)

    def __contains__(self, item: typing.Union[discord.Emoji, discord.Role, str]):
        """
        Method to check whether or not the RoleSelector class contains the specified item. This allows the support for
        "in" to be used for the class directly.

        Parameters
        ----------
        item: typing.Union[discord.Emoji, discord.Role, str]
            the item to check whether or not it exist within the class

        Returns
        -------
        bool
            result of whether or not the passed in item is stored in the class
        """
        if isinstance(item, discord.Role):
            return item in self.emote_to_role.values()
        return item in self.emote_to_role.keys()

    def __len__(self):
        """
        Method that returns the number of roles within the class

        Returns
        -------
        int
            number of roles within the RoleSelector class
        """
        return len(self.emote_to_role)

    def __str__(self):
        """
        Method that returns the data within the class in string format. This modifies the default str() for the class.

        Returns
        -------
        str
            emote and role data within the class, return "Empty" if there is no role within the class
        """
        ret = ""
        for k, i in self.emote_to_role.items():
            ret += f"{k} >> {i.mention}\n"
        return ret if len(ret) != 0 else "Empty"

    async def add_roles(self, emote: typing.Union[discord.Emoji, str], target: discord.Member):
        """
        Async method that takes passed in emote and add the appropriate role to the passed in member

        Parameters
        ----------
        emote: typing.Union[discord.Emoji, str]
            emote that the member selected, can be discord.Emoji or UTF-8 emote
        target: discord.Member
            discord member to add new role to

        Raises
        ------
        ValueError
            if there is no role associated with the passed in emote or class is set to inactive
        """
        if not self.active:
            raise ValueError("Role Selector not active")

        try:
            role = self.emote_to_role[emote]
        except KeyError:
            raise ValueError("Role not found with the given reaction")
        contains = role in target.roles

        if self.multiple:
            await target.add_roles(role, reason=f"{self.name} Role Menu [Multiple], role request")
        else:
            if not contains:
                await target.add_roles(role, reason=f"{self.name} Role Menu [Single], role request")
            remove_roles = []
            remove_emotes = []
            for k, v in self.emote_to_role.items():
                if v in target.roles and v != role:
                    remove_roles.append(v)
                    remove_emotes.append(k)

            if self.message:
                for i in remove_emotes:
                    await self.message.remove_reaction(i, target)
            await target.remove_roles(*remove_roles, reason=f"{self.name} Role Menu [Single], excess role removal")

    async def remove_roles(self, emote: typing.Union[discord.Emoji, str], target: discord.Member):
        """
        Async method that attempts to remove the role from the passed in member based on the passed in emote

        Parameters
        ----------
        emote: typing.Union[discord.Emoji, str]
            the emote associated with the role desired to remove from member
        target: discord.Member
            the member to remove roles from

        Raises
        ------
        ValueError
            if class is set to inactive or can not find the role with the passed in emote
        """
        if not self.active:
            raise ValueError("Role Selector not active")

        try:
            role = self.emote_to_role[emote]
        except KeyError:
            raise ValueError("Role not found with the given emote")

        await target.remove_roles(role, reason=f"{self.name} Role Menu, role removal request")


class RoleMenu(commands.Cog):
    """
    class inherited from commands.Cog that contains RoleMenu commands

    Attributes
    ----------
    bot: commands.Bot
        bot client reference
    data: dict
        dictionary containing all the RoleSelectors for the server
    label: dict
        dictionary containing server and the name along with the message ID of the RoleSelector
    """

    def __init__(self, bot: commands.Bot):
        """
        Constructor of RoleMenu that takes in bot from parameter to append it to self.bot

        Parameters
        ----------
        bot: commands.Bot
            bot reference
        """
        self.bot = bot
        self.data = {}
        self.label = {}
        self.db = bot.mongo["static_role"]
        self.update()

    def update(self, guild: int = None):
        """
        Method that pulls data from mongoDB collection "static_role" and populate data and label with it

        Parameters
        ----------
        guild: int
            the specific server to update if any
        """
        if guild:
            ret = self.db.find({"guild_id": guild})
            try:
                self.data[guild].clear()
            except KeyError:
                self.data.update({guild: {}})
            try:
                self.label[guild].clear()
            except KeyError:
                self.label.update({guild: {}})
        else:
            ret = self.db.find({})
            self.data.clear()
            self.label.clear()

        for i in ret:
            try:
                self.label[i["guild_id"]]
            except KeyError:
                self.label.update({i["guild_id"]: {}})
                self.data.update({i["guild_id"]: {}})
            self.label[i["guild_id"]].update({i["name"]: i["message_id"]})
            try:
                self.data[i["guild_id"]].update({i["message_id"]: RoleSelector(self.bot, i)})
            except discord.DiscordException:
                self.db.delete_many({"guild_id": i["guild_id"]})

    def search(self, guild: int, name: str):
        """
        Attempt to find the RoleMenu of the specified server and name

        Parameters
        ----------
        guild: int
            server where the RoleSelector
        name: str
            name of the role selector

        Returns
        -------

        """
        try:
            return self.data[guild][self.label[guild][name]]
        except KeyError:
            return None

    @commands.group(aliases=['rm'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def role_menu(self, ctx: commands.Context):
        """Role menu group commands. Calling this without additional parameters will bring up command help."""
        if not ctx.invoked_subcommand:
            pre = ctx.prefix

            embed = discord.Embed(
                title="`Role Menu` Command",
                colour=0x81ecec
            )
            embed.add_field(inline=False, name=f"{pre}rm l (Menu Name)",
                            value="List the menu in the server or about the mentioned role menu")
            embed.add_field(inline=False, name=f"{pre}rm c (new Menu Name)", value="Create a new role menu")
            embed.add_field(inline=False, name=f"{pre}rm + <menu name> <role mention or ID>",
                            value="Add specified role to the mentioned role menu")
            embed.add_field(inline=False, name=f"{pre}rm - <menu name> <emote/ID or role mention/ID>",
                            value="Remove the emote or role from the mentioned menu")
            embed.add_field(inline=False, name=f"{pre}rm r <menu name>",
                            value="Attempt to resolve any potential issue in that role menu")
            embed.add_field(inline=False, name=f"{pre}rm p <menu name>", value="Remove the role menu")
            embed.add_field(inline=False, name=f"{pre}rm s <menu name> <message ID> channel mention or ID)",
                            value="Set the target message to the target message, if no channel mention, then will "
                                  "attempt to scan the current channel for the message")
            embed.add_field(inline=False, name=f"{pre}rm toggle <menu name>",
                            value="Turn the mentioned role menu on or off")
            embed.add_field(inline=False, name=f"{pre}rm m <menu name>",
                            value="Switch the mentioned menu's mode between single or multiple")
            embed.add_field(inline=False, name=f"{pre}rm emote <menu name>",
                            value="Add all the reactions onto the target message for that mentioned menu")
            embed.add_field(inline=False, name=f"{pre}rm clear <menu name>",
                            value="Clear all the reactions on the target message for that mentioned menu")

            await ctx.send(embed=embed)

    @role_menu.command(aliases=['l'])
    async def list(self, ctx: commands.Context, *, name: str = None):
        """List the Role Menus within the server. If provided menu name, list emote and roles within that role menu"""
        temp = ""
        if not name:
            try:
                data = self.label[ctx.guild.id]
            except KeyError:
                return await ctx.send("This server don't have any role menus 😔")
            else:
                for i in data.keys():
                    temp += f"|> **{i}**\n"
            size = len(data.keys())
            c = 0x7ed6df
        else:
            data = self.search(ctx.guild.id, name)
            if not isinstance(data, RoleSelector):
                return await ctx.send(f"Can not find the role menu named **{name}**")
            temp = str(data)
            size = len(data)
            c = 0x55efc4 if data.active else 0xd63031
        embed = discord.Embed(
            colour=c,
            title="List of role menu(s):" if not name else f"Emotes and Roles in {name}",
            description=temp,
            timestamp=ctx.message.created_at
        ).set_footer(icon_url=self.bot.user.avatar_url_as(size=64), text=f"{size} item(s)")
        if name:
            embed.add_field(name="Mode", value="Single" if not data.multiple else "Multiple", inline=False)
        if name and data.message:
            embed.add_field(name="Target Message", value=f"[Jump Link]({data.message.jump_url})")
        if name and len(data.error) > 0:
            note = ""
            for k, i in data.error.items():
                note += f"{k} | <@&{i}> ({i})\n"
            embed.add_field(name="Error Role(s):", value=note, inline=False)

        await ctx.send(embed=embed)

    @role_menu.command(aliases=['c'])
    async def create(self, ctx: commands.Context, *, name: str):
        """Attempt to create a new role menu."""
        try:
            self.label[ctx.guild.id][name]
        except KeyError:
            pass
        else:
            return await ctx.send(f"Role menu with the name **{name}** already exists.")
        self.db.insert_one(
            {"guild_id": ctx.guild.id, "name": name, "active": False, "custom": [], "emote": [], "role_id": [],
             "message_id": ctx.message.id, "channel_id": ctx.channel.id, "multi": True}
        )
        self.update(ctx.guild.id)
        await ctx.message.add_reaction(emoji='✅')

    @role_menu.command(aliases=['+'])
    async def add(self, ctx: commands.Context, name: str, role: discord.Role):
        """Add role into the specified role menu, if successful, a reaction message will follow for the emote"""
        ret = self.search(ctx.guild.id, name)
        if not isinstance(ret, RoleSelector):
            return await ctx.send(f"Role menu **{name}** don't exists, please create it first.")
        if role in ret:
            return await ctx.send(f"`{role}` already exists within **{name}**")
        if len(ret) > 19:
            return await ctx.send(f"**{name}** menu have reached the max amount of roles")

        def check(reaction1: discord.Reaction, user1: discord.User):
            return (reaction1.message.id == message.id) and (user1.id == ctx.author.id)

        message = await ctx.send(f"React with the emote you want `{role}` to be")
        custom = False

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=check)
        except asyncio.TimeoutError:
            await message.edit(content="Emote addition timed out ⌛")
            return await message.clear_reactions()
        warn = None
        emote = reaction.emoji

        if reaction.custom_emoji:
            if emote in ret:
                await message.edit(content=f"That emote already exists within {name} role menu. "
                                           f"Please try another one.")
                return await message.clear_reactions()
            elif isinstance(emote, discord.Emoji) and emote.is_usable():
                emote = str(reaction.emoji.id)
                custom = True
                hold = reaction.emoji
                if hold.guild.id != ctx.guild.id:
                    warn = f"\n⚠ Although Hana can use {hold}, it is not from this server. It is recommended to " \
                           f"use emotes from this server so you have full control."
            else:
                await message.edit(content="Please try use emote from this server or default ones")
                return await message.clear_reactions()

        hold = reaction
        mes = ""
        await message.clear_reactions()

        if not isinstance(ret, RoleSelector):
            return await ctx.send(f"**{name}** role menu does not exists, please create it first with the create "
                                  f"command.")
        mes += f"{hold} >> `{role}` >> **{name}**"
        data = self.db.find_one({"guild_id": ctx.guild.id, "name": name})
        data['role_id'].append(role.id)
        data['custom'].append(custom)
        data['emote'].append(str(emote))
        self.db.update_one({"guild_id": ctx.guild.id, "name": name},
                           {"$set": {
                               "custom": data['custom'], "emote": data['emote'], "role_id": data['role_id']
                           }})
        self.update(ctx.guild.id)
        if warn:
            mes += warn
        await message.edit(content=mes)
        await message.clear_reactions()

    @role_menu.command(aliases=['-'])
    async def remove(self, ctx: commands.Context, name: str,
                     target: typing.Union[discord.Emoji, discord.Role, str]):
        """Remove the specified role or emote from the role menu and it's associates"""
        ret = self.search(ctx.guild.id, name)
        if not isinstance(ret, RoleSelector):
            return await ctx.send(f"Can not find role menu with the name **{name}**")
        data = self.db.find_one({"guild_id": ctx.guild.id, "name": name})
        if isinstance(target, discord.Role):
            if target not in ret:
                return await ctx.send(f"Can not find `{target}` within **{name}**")
            num = data['role_id'].index(target.id)
        else:
            if target not in ret:
                return await ctx.send(f"Can not find {target} within **{name}**")
            temp = target.id if isinstance(target, discord.Emoji) else target
            num = data['emote'].index(str(temp))

        data['custom'].pop(num)
        data['emote'].pop(num)
        data['role_id'].pop(num)
        act = data['active']
        if len(data['role_id']) < 1:
            act = False
        self.db.update_one({"guild_id": ctx.guild.id, "name": name}, {
            "$set": {"custom": data['custom'], "emote": data['emote'], "role_id": data['role_id'], "active": act}
        })
        self.update(ctx.guild.id)
        await ctx.message.add_reaction(emoji='✅')

    @role_menu.command(aliases=['r'])
    async def resolve(self, ctx: commands.Context, *, name: str):
        """Attempt to auto resolve any issue within the specified role menu"""
        find = self.search(ctx.guild.id, name)
        if not isinstance(find, RoleSelector):
            return await ctx.send(f"Can not find role menu named **{name}**")
        data = self.db.find_one({"guild_id": ctx.guild.id, "name": name})
        if not data:
            return await ctx.message.add_reaction(emoji='❌')
        if len(find.error) > 0:
            for i in find.error.values():
                num = data['role_id'].index(i)
                data['role_id'].pop(num)
                data['custom'].pop(num)
                data['emote'].pop(num)
            self.db.update_one({"guild_id": ctx.guild.id, "name": name}, {"$set": {
                "custom": data['custom'], "emote": data['emote'], "role_id": data['role_id']
            }})
            self.update(ctx.guild.id)
            await ctx.message.add_reaction(emoji='✔')
        else:
            await ctx.send(f"**{name}** contains no errors.")

    @role_menu.command(aliases=['p'])
    async def purge(self, ctx: commands.Context, *, name):
        """Delete the specified remove menu"""
        def check(reaction1: discord.Reaction, user1: discord.User):
            return (reaction1.message.id == message.id) and (user1.id == ctx.author.id) and (str(reaction1.emoji) in
                                                                                             ['✅', '❌'])

        data = self.search(ctx.guild.id, name)

        if not isinstance(data, RoleSelector):
            await ctx.send(f"**{name}** role menu does not exist")
        else:
            message = await ctx.send(f"You sure you want to delete role menu: **{name}**?")
            for i in ['✅', '❌']:
                await message.add_reaction(emoji=i)

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)
            except asyncio.TimeoutError:
                await message.edit(content="Role menu deletion timed out ⌛")
                await message.clear_reactions()
                return
            if reaction.emoji == "✅":
                self.db.delete_one({"guild_id": ctx.guild.id, "name": name})
                self.update(ctx.guild.id)
                await message.edit(content=f"Role menu - **{name}** has been purged 💥")
            if reaction.emoji == "❌":
                await message.edit(content=f"Cancelled deletion of role menu: **{name}**")
            await message.clear_reactions()

    @role_menu.command(aliases=['s'])
    async def set(self, ctx: commands.Context, name: str, mes: int, chan: discord.TextChannel = None):
        """Set the target message for the specified role menu"""
        find = self.search(ctx.guild.id, name)
        if not isinstance(find, RoleSelector):
            return await ctx.send(f"Can not find role menu with the name **{name}**")
        chan = ctx.channel if not chan else chan
        fail = False
        if not chan:
            fail = True
        else:
            mes = await chan.fetch_message(mes)
            if not mes:
                fail = True
        if fail:
            return await ctx.send("Can not find the target message")
        if chan.id == find.channel_id and mes.id == find.message_id:
            return await ctx.send(f"Received same input as one stored in system, no changes made.")
        try:
            if mes.id in self.label[ctx.guild.id].values():
                return await ctx.send("The target message is current in use by another role menu, action cancelled")
        except KeyError:
            pass
        self.db.update_one({"guild_id": ctx.guild.id, "name": name}, {"$set": {
            "message_id": mes.id, "channel_id": chan.id
        }})
        self.update(ctx.guild.id)
        await ctx.message.add_reaction(emoji='✅')

    @role_menu.command(aliases=['t'])
    async def toggle(self, ctx: commands.Context, *, name: str):
        """Toggle the specified role menu on/off"""
        data = self.search(ctx.guild.id, name)
        if not isinstance(data, RoleSelector):
            return await ctx.send(f"Can not find role menu named **{name}**")
        if len(data) < 1:
            return await ctx.send(f"Role menu **{name}** does not contain any item, toggle failed.")
        if not data.message:
            data.active = False
            await ctx.send(f"Can not locate the target message for role menu **{name}**, toggle failed")
        else:
            data.active = not data.active
            await ctx.message.add_reaction(emoji='✅')
        self.db.update_one({"guild_id": ctx.guild.id, "name": name}, {"$set": {
            "active": data.active
        }})

    @role_menu.command(aliases=['m'])
    async def mode(self, ctx: commands.Context, *, name: str):
        """Toggle the mode of the specified role menu between single or multiple"""
        data = self.search(ctx.guild.id, name)
        if not isinstance(data, RoleSelector):
            return await ctx.send(f"Can not find role menu named **{name}**")
        data.multiple = not data.multiple
        self.db.update_one({"guild_id": ctx.guild.id, "name": name}, {"$set": {
            "multi": data.multiple
        }})
        await ctx.message.add_reaction(emoji='✌' if data.multiple else '☝')

    @role_menu.command(aliases=['e'])
    async def emote(self, ctx: commands.Context, *, name: str):
        """Populate the target message with reactions of the specified role menu"""
        data = self.search(ctx.guild.id, name)
        if not isinstance(data, RoleSelector):
            return await ctx.send("Can not locate that role menu")
        for i in data.emote_to_role.keys():
            await data.message.add_reaction(emoji=i)
        await ctx.message.add_reaction(emoji='✅')

    @role_menu.command()
    async def clear(self, ctx: commands.Context, *, name: str):
        """Clear the reaction of the target message of the specified role menu"""
        data = self.search(ctx.guild.id, name)
        if not isinstance(data, RoleSelector):
            return await ctx.send(f"Can not find role menu named **{name}**")
        await data.message.clear_reactions()
        await ctx.message.add_reaction(emoji='✅')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        Async event listener that will be called when bot detected any added reaction to a message, and then determine
        whether or not that reaction were a role menu request for role addition

        Parameters
        ----------
        payload: discord.RawReactionActionEvent
            payload data of the added reaction
        """
        try:
            data = self.data[payload.guild_id][payload.message_id]
        except KeyError:
            return
        if data.active and data.message:
            member = payload.member
            if member.bot:
                return
            try:
                temp = payload.emoji.name if payload.emoji.is_unicode_emoji() else self.bot.get_emoji(payload.emoji.id)
                await data.add_roles(temp, member)
            except ValueError:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """
        Async event listener that will be called when bot detected any removed reaction from a message, and then
        determine whether or not that reaction were a role menu request for role removal

        Parameters
        ----------
        payload: discord.RawReactionActionEvent
            payload data of the removed reaction
        """
        try:
            data = self.data[payload.guild_id][payload.message_id]
        except KeyError:
            return
        if data.active:
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                emote = payload.emoji.name if payload.emoji.is_unicode_emoji() else self.bot.get_emoji(payload.emoji.id)
                member = guild.get_member(payload.user_id)
                if member:
                    await data.remove_roles(emote, member)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """
        Async event listener that will be called when bot detects any message deletion. Determine whether or not the
        deleted message were a stored target message for a role menu within the system, and change state for that role
        menu to avoid errors.

        Parameters
        ----------
        payload: discord.RawMessageDeleteEvent
            payload data for the deleted message
        """
        try:
            data = self.data[payload.guild_id][payload.message_id]
        except KeyError:
            return
        if data.message:
            data.active = False
            data.message = None
