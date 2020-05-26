import re
import sys
import typing
import asyncio
import discord
import datetime
from discord.ext import commands, tasks
from cogs.Admin.Management import is_admin


def setup(bot: commands.Bot):
    bot.add_cog(Test(bot))
    print("Loaded Cog:\tTest")


def teardown(bot: commands.Bot):
    bot.remove_cog("Test")
    print("Unloaded Cog:\tTest")


class Test(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
