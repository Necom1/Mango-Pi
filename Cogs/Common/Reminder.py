import discord
import asyncio
from discord.ext import commands
from Components.DelayedTask import time_converter
from Components.RemindTimer import RemindTimer, dm_remind
from Components.MangoPi import MangoPi


async def setup(bot: MangoPi):
    """
    Essential function for Cog loading that calls the update method of Reminder Cog (to fetch data from Mongo)
    before adding it to the bot.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to append the Cog
    """
    await bot.add_cog(Reminder(bot))
    print("Load Cog:\tReminder")


async def teardown(bot: MangoPi):
    """
    Method for Cog unload, this function will print to Console that Reminder Cog got unload.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to unload the Cog
    """
    await bot.remove_cog("Reminder")
    print("Unload Cog:\tReminder")


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
    def __init__(self, bot: MangoPi):
        """
        Constructor for Reminder class.

        Parameters
        ----------
        bot : MangoPi
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

    async def cog_check(self, ctx: commands.Context):
        """
        Async method that does the command check before running

        Parameters
        ----------
        ctx: commands.Context
            pass in context to check

        Returns
        -------
        bool
            whether or not to run commands within this Cog
        """
        return not self.bot.ignore_check(ctx)

    @commands.command(aliases=['remindme'])
    async def remind_me(self, ctx: commands.Context, time: str, *, remind: str = ""):
        """Commands that sets reminder for user. Maximum of 10 reminders."""
        if len(remind) == 0:
            return await ctx.reply("Please input remind detail.")
        if len(remind) > 500:
            return await ctx.reply("Too long of a reminder... Try keep it under 500 words...")

        try:
            end = time_converter(time, ctx.message.created_at)
        except ValueError as e:
            return await ctx.reply(str(e.args[0]))

        try:
            self.memory[ctx.author.id]
        except KeyError:
            self.memory.update({ctx.author.id: {}})
        data = self.memory[ctx.author.id]
        if len(data) >= 10:
            return await ctx.reply("Max 10 reminder~")
        insert = RemindTimer(self.bot, ctx.message.id, end, remind, ctx.author.id)
        data.update({ctx.message.id: insert})
        self.db.insert_one({"_id": ctx.message.id, "user_id": ctx.author.id, "details": remind, "end": end})
        await ctx.message.add_reaction(emoji='👌')

    @commands.group(aliases=['reminders'])
    async def reminder(self, ctx: commands.Context):
        """Group command that will list all the reminders if not additional sub-command are received."""
        if not ctx.invoked_subcommand:
            try:
                data = self.memory[ctx.author.id]
            except KeyError:
                return await ctx.reply("No reminder in place!")
            if len(data) == 0:
                return await ctx.reply("No reminder in place!")
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
            await ctx.reply(embed=embed)

    @reminder.command(aliases=['-'])
    async def remove(self, ctx: commands.Context, reminder_id: int):
        """Sub-command of reminder that removes a reminder base on it's ID."""
        try:
            data = self.memory[ctx.author.id][reminder_id]
        except KeyError:
            return await ctx.reply("Can not find the reminder")
        await data.terminate()
        await ctx.message.add_reaction(emoji='👌')
