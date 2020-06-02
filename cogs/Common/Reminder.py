import discord
import asyncio
import datetime
from discord.ext import commands
from misc.Blueprints import DelayedTask, time_converter


def setup(bot: commands.Bot):
    """
    Essential function for Cog loading that calls the update method of Reminder Cog (to fetch data from Mongo)
    before adding it to the bot.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to append the Cog
    """
    bot.add_cog(Reminder(bot))
    print("Load Cog:\tReminder")


def teardown(bot: commands.Bot):
    """
    Method for Cog unload, this function will print to Console that Reminder Cog got unload.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to unload the Cog
    """
    bot.remove_cog("Test")
    print("Unload Cog:\tReminder")


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


class Reminder(commands.Cog):
    """
    Class inherited from commands.Cog that contains reminder commands.

    Attributes
    ----------
    bot : commands.Bot
        bot reference
    db : MongoClient
        mongoDB client pointing to "reminders" collection
    memory : dict
        dictionary storing all the reminder event
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor for Reminder class.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference for self.bot
        """
        self.bot = bot
        self.db = bot.mongo["reminders"]
        self.memory = {}
        self.update()

    def update(self):
        """
        Method that populates memory from "reminders" collection of mongoDB
        """
        late_reminders = []
        self.memory.clear()
        data = self.db.find({})
        for i in data:
            user = self.bot.get_user(i['user_id'])
            if user:
                try:
                    self.memory[user.id]
                except KeyError:
                    self.memory.update({user.id: {}})
                try:
                    insert = RemindTimer(bot=self.bot, pack=i)
                except ValueError:
                    late_reminders.append(i)
                    self.db.delete_one({"_id": i['_id']})
                else:
                    self.memory[i['user_id']].update({i['_id']: insert})
            else:
                self.db.delete_many(i['user_id'])
        for i in late_reminders:
            asyncio.get_event_loop().create_task(dm_remind(self.bot, i['user_id'], i['details'], True))

    @commands.command(aliases=['remindme'])
    async def remind_me(self, ctx: commands.Context, time: str, *, remind: str = ""):
        """Commands that sets reminder for user. Maximum of 10 reminders."""
        if self.bot.ignore_check(ctx):
            return
        if len(remind) == 0:
            return await ctx.send("Please input remind detail.")
        if len(remind) > 500:
            return await ctx.send("Too long of a reminder... Try keep it under 500 words...")

        try:
            end = time_converter(time, ctx.message.created_at)
        except ValueError as e:
            return await ctx.send(str(e.args[0]))

        try:
            self.memory[ctx.author.id]
        except KeyError:
            self.memory.update({ctx.author.id: {}})
        data = self.memory[ctx.author.id]
        if len(data) >= 10:
            return await ctx.send("Max 10 reminder~")
        insert = RemindTimer(self.bot, ctx.message.id, end, remind, ctx.author.id)
        data.update({ctx.message.id: insert})
        self.db.insert_one({"_id": ctx.message.id, "user_id": ctx.author.id, "details": remind, "end": end})
        await ctx.message.add_reaction(emoji='👌')

    @commands.group(aliases=['reminders'])
    async def reminder(self, ctx: commands.Context):
        """Group command that will list all the reminders if not additional sub-command are received."""
        if self.bot.ignore_check(ctx):
            return
        if not ctx.invoked_subcommand:
            try:
                data = self.memory[ctx.author.id]
            except KeyError:
                return await ctx.send("No reminder in place!")
            if len(data) == 0:
                return await ctx.send("No reminder in place!")
            counter = 1
            embed = discord.Embed(
                title="Upcoming Reminders",
                colour=0x8c7ae6,
                timestamp=ctx.message.created_at
            )
            for i in data.keys():
                embed.add_field(inline=False,
                                name=f"Reminder {counter} - ID: __{i}__",
                                value=f"{data[i].end.strftime('%B %#d, %Y | `%I:%M %p` UTC')}\n**{data[i].details}**")
            await ctx.send(embed=embed)

    @reminder.command(aliases=['-'])
    async def remove(self, ctx: commands.Context, reminder_id: int):
        """Sub-command of reminder that removes a reminder base on it's ID."""
        if self.bot.ignore_check(ctx):
            return
        try:
            data = self.memory[ctx.author.id][reminder_id]
        except KeyError:
            return await ctx.send("Can not find the reminder")
        await data.terminate()
        await ctx.message.add_reaction(emoji='👌')
