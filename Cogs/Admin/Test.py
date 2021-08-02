import re
import os
import sys
import typing
import asyncio
import discord
import datetime
import requests
from discord.ext import commands, tasks
from Components.MangoPi import MangoPi, is_admin
from Components.MessageTools import image_check


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
    @commands.check(is_admin)
    async def er(self, ctx: commands.Context):
        """raises error to test"""
        raise Exception("LOL")
