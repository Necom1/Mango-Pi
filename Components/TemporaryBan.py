import asyncio
import discord
import datetime
from discord.ext import commands
from Components.DelayedTask import DelayedTask


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
