import typing
import asyncio
import discord
from discord.ext import commands


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
        Async method that removes reaction of users no longer in the guild. A lot of API calls

        Parameters
        ----------
        safe: int
            bot ID to ignore
        """
        if not self.message or not self.active:
            return

        for reaction in self.message.reactions:
            async for i in reaction.users():
                if i.id != safe:
                    if isinstance(i, discord.User):
                        # not longer part of the server
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

        temp = "Multiple" if self.multiple else "Single"
        await target.add_roles(role, reason=f"{self.name} Role Menu [{temp}], role request")

        if not self.multiple:
            if not contains:
                await target.add_roles(role, reason=f"{self.name} Role Menu [Single], role request")

            remove_roles = []
            for k, v in self.emote_to_role.items():
                if v in target.roles and v != role:
                    remove_roles.append(v)

            if len(remove_roles) > 0:
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

        if role in target.roles:
            await target.remove_roles(role, reason=f"{self.name} Role Menu, role removal request")
