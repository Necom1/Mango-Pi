import asyncio
import discord
import datetime
from discord.ext import commands
from Components.DelayedTask import DelayedTask


async def dm_remind(bot: commands.Bot, user_id: int, details: str, late: bool = False):
    """
    Function that will send reminder to the specified user in embed format.

    Parameters
    ----------
    bot : commands.Bot
        bot reference for finding user and modify mongoDB
    user_id : int
        ID of the user to remind
    details : str
        reminder details
    late : bool
        whether or not the reminder was late, used to append additional info on the embed
    """
    user = bot.get_user(user_id)
    if not user:
        try:
            bot.get_cog("Reminder").memory.pop(user_id)
            bot.mongo["reminders"].delete_many({"user_id": user_id})
        except KeyError:
            pass
        return
    embed = discord.Embed(
        colour=0xfffa65,
        title="⏰ Reminder ⏰",
        description=details
    )
    if late:
        embed.set_footer(text="late reminder due to Cog downtime")
    try:
        await user.send(embed=embed)
    except discord.HTTPException or discord.Forbidden:
        pass


class RemindTimer(DelayedTask):
    """
    A class inherited from DelayedTask class. This class will process the reminders.

    Attributes
    ----------
    bot : commands.Bot
        bot reference
    details : str
        reminder details
    user_id : int
        user ID for the reminder
    identity : int
        ID for the reminder (the message ID sent by the user as reminder request)
    """
    def __init__(self, bot: commands.Bot, me: int = None, end: datetime.datetime = None, details: str = None,
                 user: int = None, pack: dict = None):
        """
        Constructor for RemindTimer that takes in bot, me, end, details, and user information; or bot and pack. This
        constructor will start the scheduled task.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference
        me : int
            message ID / the reminder ID
        end : datetime.datetime
            date set for the reminder
        details : str
            the reminder detail / what to remind the user
        user : int
            ID of the user to remind
        pack
            data from MongoDB
        """
        self.bot = bot
        if pack:
            self.details = pack["details"]
            self.user_id = pack["user_id"]
            self.identity = pack["_id"]
            DelayedTask.__init__(self, pack["end"])
        else:
            self.details = details
            self.user_id = user
            self.identity = me
            DelayedTask.__init__(self, end)
        self.begin()

    async def on_exit(self):
        """
        Method that will be called upon exiting the task. This method will remove the reminder from mongo and memory.
        """
        try:
            self.bot.get_cog("Reminder").memory[self.user_id].pop(self.identity)
            self.bot.mongo["reminders"].delete_one({"_id": self.identity})
        except KeyError:
            pass

    async def task(self):
        """
        Method of the task for this class. This will call upon the dm_remind after specified amount of time.
        """
        await asyncio.sleep(self.seconds)
        await dm_remind(self.bot, self.user_id, self.details)
        await self.on_exit()
