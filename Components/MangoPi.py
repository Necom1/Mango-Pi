import os
import json
import random
import discord
import asyncio
import datetime
import platform
import traceback
from pymongo import MongoClient
from discord.ext import commands
from Components.BotData import BotData
from Components.KeyReader import KeyReader
from Components.HelpMenu import CustomHelpCommand
from Components.PrintColor import PrintColors as Colors
from Components.MessageTools import embed_message, split_string


def offline(ctx: commands.Context, ignore_dm: bool = False):
    """
    A function that checks if DM is ignored. This is only used when Ignore Cog is offline.

    Parameters
    ----------
    ctx : commands.Context
        pass in context for analysis
    ignore_dm : bool
        whether or not the command is being ignored in direct messages

    Returns
    -------
    bool
        Whether or not that channel is ignored
    """
    if not ctx.guild:
        return ignore_dm

    return False


def is_admin(ctx: commands.Context):
    """
    Function that returns the Admin class check result for commands.Check

    Parameters
    ----------
    ctx : commands.Context
        pass in context to check

    Returns
    -------
    bool
        Whether or not the author is an admin
    """
    return ctx.bot.data.staff_check(ctx.author.id)


class MangoPi(commands.Bot):

    def __del__(self):
        print(Colors.BLUE + Colors.BOLD + "Bot Terminated" + Colors.END)

    def __init__(self):
        self.ignore_check = offline
        self._first_ready = True
        self._separator = "---------------------------------------------------------"

        print("=========================================================\n"
              f"Now Starting Bot\t|\t{platform.system()}\n{self._separator}")

        data = KeyReader()

        self.mongo = MongoClient(data.db_address)[data.cluster]
        self.default_prefix = data.prefix
        self.loaded_cogs = {}
        self.unloaded_cogs = {}

        intents = discord.Intents(
            guilds=True,
            members=True,
            bans=True,
            emojis=True,
            voice_states=True,
            messages=True,
            guild_reactions=True
        )

        super().__init__(self, help_command=CustomHelpCommand(), prefix=commands.when_mentioned_or(data.prefix),
                         intents=intents)

        self.app_info = None
        self.data = None

        self.run(data.bot_token)

    def _load_all_cogs(self, location: str = './Cogs', note: str = 'Cogs'):
        """
        A protected method that attempt to load cogs within the specified directory.

        Parameters
        ----------
        location : str
            the directory to scan
        note : str
            String necessary for loading cog according to location
        """
        # load all the Cogs inside that directory
        for root, dirs, files in os.walk(location):
            # Scan sub-directories for potential Cogs
            for i in dirs:
                if not i.startswith('__'):
                    new_location = f"{location}/{i}"
                    new_note = f"{note}.{i}"
                    self._load_all_cogs(new_location, new_note)

            for i in files:
                if i.endswith(".py") and not i.startswith("!") and i.replace(".py", "") not in self.loaded_cogs.keys():
                    element = i.replace('.py', '')
                    temp = f"{note}.{element}"

                    try:
                        self.load_extension(temp)
                        self.loaded_cogs[element] = temp
                    except commands.NoEntryPointError:
                        print(f"{Colors.FAIL}failed to load, missing setup function{Colors.FAIL}")
                    except Exception:
                        self.unloaded_cogs[element] = temp
                        print(f"{Colors.FAIL}{location}/{i} Cog has failed to load with error:{Colors.END}")
                        traceback.print_exc()
                        # traceback.format_exc()

    async def on_ready(self):
        if self._first_ready:
            self.app_info = await self.application_info()
            self.data = BotData(self)

            print(f"Attempting to load all Cogs\n{self._separator}")
            self._load_all_cogs()

            print("=========================================================\n"
                  "\t\tSuccessfully logged into Discord\n"
                  "*********************************************************\n"
                  f"Bot:\t| \t{self.user.name}\t({self.user.id})\n"
                  f"Owner:\t| \t{self.app_info.owner}\t({self.app_info.owner.id})\n"
                  "*********************************************************\n"
                  "\t\tInitialization complete, ready to go\n"
                  "=========================================================\n")

            self._first_ready = False

    async def on_resumed(self):
        print(f"{self._separator}\n\tBot Session Resumed\n{self._separator}")

    async def on_connect(self):
        print(f"\tConnected to Discord\n{self._separator}")

    async def on_disconnect(self):
        print(f"{self._separator}\n\tDisconnected from Discord\n{self._separator}")

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """
        A method that will be called when bot encounters an error.

        Parameters
        ----------
        ctx : commands.Context
            passing in the error context
        error : Exception
            the error

        Raises
        ------
        commands.errors
            when error that isn't caught
        """
        # Send appropriate error message on command error
        # Help From Commando950#0251 (119533809338155010) > https://github.com/Commando950
        safe = (commands.MissingPermissions,
                commands.CheckFailure)
        if isinstance(error, safe):
            return

        if isinstance(error, (commands.CommandNotFound, commands.BadArgument, commands.errors.MissingRequiredArgument,
                              discord.ext.commands.errors.BadUnionArgument)):
            emote = "😕"
            if isinstance(error, commands.CommandNotFound):
                emote = "❓"
            try:
                await ctx.message.add_reaction(emoji=emote)
                await asyncio.sleep(5)
                await ctx.message.remove_reaction(emoji=emote, member=ctx.bot.user)
            except (discord.HTTPException, discord.Forbidden):
                pass
            return

        print(f"{Colors.WARNING}{ctx.channel} > {ctx.author} : {ctx.message.content}{Colors.END}")

        targets = self.data.get_report_channels()

        if len(targets) > 0:
            try:
                raise error
            except Exception:
                mes = split_string(f"{traceback.format_exc()}", 1900)

            for i in targets:
                embeds = embed_message(self, ctx.message, True)
                first = True
                for k in embeds:
                    await i.send(content="Error has occurred while running this command" if first else None, embed=k)
                    first = False
                count = 1
                for k in mes:
                    await i.send(f"Error Traceback Page **{count}**:\n```python\n{k}\n```")
                    count += 1

        await ctx.message.add_reaction(emoji='⚠')
        raise error
