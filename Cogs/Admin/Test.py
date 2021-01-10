import re
import sys
import typing
import asyncio
import discord
import datetime
from discord.ext import commands, tasks
from Components.MangoPi import MangoPi, is_admin


def setup(bot: commands.Bot):
    bot.add_cog(Test(bot))
    print("Load Cog:\tTest")


def teardown(bot: commands.Bot):
    bot.remove_cog("Test")
    print("Unload Cog:\tTest")


class Test(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def test(self, ctx: commands.Context):
        raise ValueError("Error Test")
