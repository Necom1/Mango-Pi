import discord
import asyncio
import datetime
from discord.ext import commands
from Components.DelayedTask import DelayedTask


async def remove_mute(bot: commands.Bot, guild: int, target: int, reason: str = "Mute time expired"):
    """
    Async function to remove a mute role from the user.

    Parameters
    ----------
    bot: commands.Bot
        pass in bot for modifying mongo
    guild: int
        ID of the server
    target: int
        ID of the unmute target
    reason: str
        reason for the role removal, default is "Mute time expired"
    """
    mute = bot.get_cog("Mute")

    def mass_delete():
        try:
            mute.timers.pop(guild)
            mute.roles.pop(guild)
        except KeyError:
            pass
        bot.mongo["mute_time"].delete_many({"guild_id": guild})
        bot.mongo["mute_role"].delete_many({"_id": guild})

    server = bot.get_guild(guild)
    if not server:
        mass_delete()
    else:
        try:
            role = mute.roles[guild]
        except KeyError:
            mass_delete()
        else:
            member = server.get_member(target)
            try:
                if member:
                    if role in member.roles:
                        try:
                            await member.remove_roles(role, reason=reason)
                        except discord.HTTPException:
                            raise ValueError("remove request")
                    else:
                        raise ValueError("remove request")
                else:
                    raise ValueError("remove request")
            except ValueError:
                bot.mongo["mute_time"].delete_one({"guild_id": guild, "user_id": target})


class MuteTimer(DelayedTask):
    """
    Class inherited from DelayedTask. Holds function necessary for automatic role removal.

    Attributes
    ----------
    bot: commands.Bot
        bot reference
    guild: int
        server ID
    member: int
        ID of the muted server member
    reason: int
        reason for the mute
    """

    def __init__(self, bot: commands.Bot, guild_id: int = None, user_id: int = None, end: datetime.datetime = None,
                 reason: str = "", pack: dict = None):
        """
        Constructor for MuteTimer class

        Parameters
        ----------
        bot: commands.Bot
            pass in bot reference
        guild_id: int
            ID of the server for the mute timer
        user_id: int
            ID of the muted user
        end: datetime.datetime
            the target time when the mute expires
        reason: str
            reason for the mute
        pack
            class can be initialized through data passed from mongo along with passed in bot reference
        """
        self.bot = bot
        if pack:
            self.guild = pack["guild_id"]
            self.member = pack["user_id"]
            self.reason = pack["reason"]
            DelayedTask.__init__(self, pack["end"])
        else:
            self.guild = guild_id
            self.member = user_id
            self.reason = reason
            DelayedTask.__init__(self, end)
        self.begin()

    async def task(self):
        """
        Async method containing the process to execute (removing mute from the specified user) after reaching said time.
        """
        await asyncio.sleep(self.seconds)
        await remove_mute(self.bot, self.guild, self.member)
        await self.on_exit()

    async def on_exit(self):
        """
        Async method to execute when exiting the mute timer, this removes the mute timer from dictionary within Mute
        Cog and mongo.
        """
        try:
            self.bot.get_cog("Mute").timers[self.guild].pop(self.member)
            self.bot.mongo["mute_time"].delete_one({"guild_id": self.guild, "user_id": self.member})
        except KeyError:
            pass
