import typing
import asyncio
import discord
import datetime
from discord.ext import commands


def to_mention_list(data: list):
    """
    Convert the passed in list of members to list of string

    Parameters
    ----------
    data: list
        list of members

    Returns
    -------
    list
        list containing split up strings of mentioned members
    """
    ret = []
    temp = ""
    count = 1
    for i in data:
        temp += f"{count}. \t{i.mention}\n"
        if count % 20 == 0:
            ret.append(temp)
            temp = ""
        count += 1
    if temp != "":
        ret.append(temp)
    return ret


class RaidFilter:
    """
    Class RaidFilter that takes in data from Mongo to build an anti-raid system for the server.

    Attributes
    ----------
    bot: commands.Bot
        bot reference
    in_progress: bool
        whether or not there is a loop in progress for timeout delay
    raiders: dict
        dictionary containing potential raider member data
    holding: dict
        dictionary of temporary holding cell for newly joined members, will be release if system is not triggered
        within set intervals
    raid: bool
        whether or not system have detected an raid
    role_id: int
        ID of the raider role of the server
    switch: bool
        indicator for anti-raid state (on/off)
    guild_id: int
        ID of the server associated with the anti-raid system
    count: int
        amount of newly joined members within the holding cell needed to trigger the system
    interval: int
        integer of seconds before the newly joined member is removed from holding cell
    timeout: int
        integer of seconds of period of no new member for the system to auto turn off raid mode
    server: discord.Guild
        guild reference of the anti-raid
    role: discord.Role
        the raider role reference for that server
    """
    def __init__(self, bot: commands.Bot, package: dict):
        """
        Constructor for RaidFilter class

        Parameters
        ----------
        bot: commands.Bot
            pass in bot reference for self.bot
        package
            pass in Mongo data for class value initialization
        """
        self.bot = bot
        self.in_progress = False
        self.time = None
        self.raiders = {}
        self.holding = {}
        self.raid = False
        self.role_id = package["role_id"]
        self.switch = package["power"]
        self.guild_id = package["_id"]
        self.count = package["amount"]
        self.interval = package["interval"]
        self.timeout = package["timeout"]
        self.server = bot.get_guild(self.guild_id)
        if not self.server:
            raise ValueError(f"Can not find the server with the ID: {self.guild_id}")
        self.role = self.server.get_role(self.role_id)
        if not self.role:
            raise ValueError(f"Can not find the role (ID: {self.role}) for the {self.server.name}")
        for i in self.role.members:
            self.raiders.update({i.id: i})

    async def update_role(self, role: discord.Role):
        """
        Method to update self.role and self.role_id with the role inputted from parameter

        Parameters
        ----------
        role: discord.Role
            the new raider role to change the anti-raid system to
        """
        for i in self.raiders.values():
            await i.add_roles(role, reason="Updated raider role - add new role")
            await i.remove_roles(self.role, reason="Updated raider role - remove old one")
        if self.role != role:
            self.role = role
            self.role_id = role.id

    async def alarm(self, raiders: list):
        """
        Async method that takes passed in list of raider and sends it to the appropriate logging channel

        Parameters
        ----------
        raiders: list
            list of raiders for notifying
        """
        for k in raiders:
            embed = discord.Embed(
                colour=0xe056fd,
                title="Potential Raider",
                timestamp=k.joined_at
            ).set_footer(text="Joined", icon_url=self.server.icon_url_as(size=64))
            embed.set_thumbnail(url=k.avatar_url)
            embed.add_field(name="Mention", value=k.mention)
            embed.add_field(name="ID", value=k.id)
            await self.notification(embed)

    async def timeout_alert(self, manual: bool = False):
        """
        Async method sending embed of raid mode being turned off to the appropriate channel

        Parameters
        ----------
        manual: bool
            whether or not a user specified the raid mode to turn off
        """
        if not self.in_progress and not self.raid:
            embed = discord.Embed(
                colour=0x55efc4,
                title="Coast is Clear",
                timestamp=datetime.datetime.utcnow(),
                description=f"No new joins within {self.timeout} seconds, system back to green." if not manual else
                "System back to green, raid alert stopped manually."
            ).set_footer(text="Lockdown lifted @", icon_url=self.server.icon_url_as(size=64))
            await self.notification(embed)

    async def notification(self, message: typing.Union[discord.Embed, str]):
        """
        Async method that will attempt to gather data from Logging Cog and send the passed in message to the "raid"
        notification channels.

        Parameters
        ----------
        message: typing.Union[discord.Embed, str]
            message to send
        """
        try:
            data = self.bot.get_cog("Logging").memory[self.guild_id]
        except ValueError:
            return
        except KeyError:
            return
        for i in data:
            channel = self.bot.get_channel(i.channel)
            if channel and i.data['raid']:
                await channel.send(content=message if isinstance(message, str) else None,
                                   embed=message if isinstance(message, discord.Embed) else None)

    async def triggered(self, indefinite: bool = False):
        """
        Async method that will turn on raid mode and shift all members within the holding cell to raid cell along with
        giving them the raider role.

        Parameters
        ----------
        indefinite: bool
            Whether or not the "turn on raid mode" is called by the user, if so then there won't be a auto timeout
        """
        if not indefinite:
            self.time = datetime.datetime.utcnow()
        self.raid = True
        temp = list(self.holding.values())
        self.holding.clear()
        for i in temp:
            if self.role not in i.roles:
                try:
                    await i.add_roles(self.role, reason="Potential Raider")
                    self.raiders[i.id] = i
                except discord.NotFound:
                    pass
        await self.alarm(temp)
        if self.time and not self.in_progress:
            await self.countdown()

    async def countdown(self):
        """
        Async method that will turn off raid mode automatically if there is no new member

        Raises
        ------
        ValueError
            if there is also a instance of this method running
        """
        if not self.switch:
            return
        if self.in_progress:
            raise ValueError("Timer in progress, no need to call another one")
        self.in_progress = True
        while self.raid and (self.time + datetime.timedelta(seconds=self.timeout) > datetime.datetime.utcnow()) \
                and self.switch:
            await asyncio.sleep(1)
        manual = False
        if not self.raid:
            manual = True
        self.time = None
        self.raid = False
        self.in_progress = False
        await self.timeout_alert(manual)

    async def add(self, member: discord.Member, reason: str = "Marked raider"):
        """
        Async method that will attempt to add the passed in member into the raider cell and append the raider role

        Parameters
        ----------
        member: discord.Member
            the member to add to the raid cell
        reason: str
            reason for adding the member to the raid cell

        Raises
        ------
        ValueError
            if the passed in member is already inside the raid cell
        """
        if member.id in self.raiders.keys():
            raise ValueError("Is already a raider")
        else:
            self.raiders.update({member.id: member})
        if self.role not in member.roles:
            try:
                await member.add_roles(self.role, reason=reason)
            except discord.HTTPException:
                pass

    async def remove(self, member: discord.Member, reason: str = "Unmark raider"):
        """
        Async method that removes the passed in member from the raid cell along with removing the raider role

        Parameters
        ----------
        member: discord.Member
            the target to remove from the raid cell
        reason: str
            reason for the removal

        Raises
        ------
        ValueError
            if the passed in member can't be found within the raid cell
        """
        if member.id in self.raiders.keys():
            self.raiders.pop(member.id)
        else:
            raise ValueError("Can not find raider")
        if self.role in member.roles:
            try:
                await member.remove_roles(self.role, reason=reason)
            except discord.HTTPException:
                pass

    async def new_member(self, member: discord.Member):
        """
        Async method that passes in the newly joined member from parameter into the holding cell or raid cell
        depending on the mode at the time.

        Parameters
        ----------
        member: discord.Member
            the newly joined member
        """
        if not self.switch:
            return
        if member.id in self.raiders.keys():
            try:
                await member.add_roles(self.role, reason="Marked raider rejoined")
            except discord.HTTPException:
                pass
        else:
            self.holding[member.id] = member
            if self.raid:
                self.holding.pop(member.id)
                self.time = datetime.datetime.utcnow()
                await self.add(member, "Potential raider")
                await self.alarm([member])
            else:
                if len(self.holding) >= self.count:
                    await self.triggered()
                else:
                    await asyncio.sleep(self.interval)
                    if not self.raid:
                        try:
                            self.holding.pop(member.id)
                        except KeyError:
                            pass

    def raiders_to_string(self):
        """
        Method that converts the current raid cell into a list of string

        Returns
        -------
        list
            the raid cell member mention separated by 20 per array slot
        """
        return to_mention_list(list(self.raiders.values()))

    def holding_to_string(self):
        """
        Method that converts the current holding cell cell into a list of string

        Returns
        -------
        list
            the holding cell member mention separated by 20 per array slot
        """
        return to_mention_list(list(self.holding.values()))

    async def ban_all(self, ctx: commands.Context, stop: bool = True):
        """
        Async method to ban all members within the raid cell.

        Parameters
        ----------
        ctx: commands.Context
            pass in context for process
        stop: bool
            whether or not to turn off the raid mode, default to yes

        Returns
        -------
        list:
            list of banned members after
        """
        for i in self.raiders.values():
            try:
                await i.ban(reason="Raider ban")
            except discord.HTTPException:
                user = ctx.bot.get_user(i.id)
                await ctx.guild.ban(user, reason="Raider ban")

        ret = self.raiders_to_string()
        self.raiders.clear()
        self.raid = not stop
        return ret

    async def kick_all(self, stop: bool = False):
        """
        Async method to kick all members within the raid cell.

        Parameters
        ----------
        stop: bool
            whether or not to stop the raid mode after, default is no

        Returns
        -------
        list
            list of kicked member after
        """
        for i in self.raiders.values():
            try:
                await i.kick(reason="Raider kick")
            except discord.HTTPException:
                pass

        ret = self.raiders_to_string()
        self.raiders.clear()
        self.raid = not stop
        return ret

    def toggle(self):
        """
        Method to toggle on or off the anti-raid class

        Returns
        -------
        bool
            the new updated status of the RaidFilter
        """
        self.switch = not self.switch
        return self.switch

    async def release_all(self, stop: bool = True):
        """
        Async method to free all members within the raid cell

        Parameters
        ----------
        stop: bool
            whether or not to stop the raid mode after, default is yes

        Returns
        -------
        list
            list of freed member from the raid cell
        """
        self.raid = not stop
        for i in self.raiders.values():
            if self.role in i.roles:
                try:
                    await i.remove_roles(self.role, reason="Release marked raiders. All clear, not a raid.")
                except discord.NotFound:
                    pass

        ret = self.raiders_to_string()
        self.raiders.clear()
        return ret
