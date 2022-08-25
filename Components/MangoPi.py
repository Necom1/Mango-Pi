import os
import sys
import discord
import asyncio
import datetime
import platform
import traceback
from discord.ext import commands
from pymongo import errors, MongoClient
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


def highest_role_position(arr: list):
    """
    Function that takes in an array of discord Roles and return the int of the highest position from all those roles

    Parameters
    ----------
    arr: list
        the array of discord roles

    Returns
    -------
    int
        the highest position found within the array of discord roles
    """
    ret = 0
    for i in arr:
        if i.position > ret:
            ret = i.position

    return ret


class MangoPi(commands.Bot):
    """
    MangoPi class inherited from commands.Bot class

    Attributes
    ----------
    last_dc : datetime.datetime
        UTC time of when did the bot last disconnected from discord
    ignore_check : def
        ignore check function of the bot
    _first_ready : bool
        private variable that defines whether or not this is bot's first ready
    _separator : str
        separator string
    mongo : MongoClient
        the connection to bot's MongoDB via MongoClient
    default_prefix : str
        string of bot's default prefix
    loaded_cogs : dict
        dictionary of strings that for bot's loaded Cogs
    unloaded_cogs : dict
        dictionary of strings for unloaded Cogs
    app_info : discord.AppInfo
        discord application info fetched from API or none
    data : BotData
        BotData class reference for remembering bot admins
    dc_report : bool
        whether or not to report bot disconnection (typically less than a second dc)
    """

    def __del__(self):
        """
        Overrides default __del__ method to print a bot termination message
        """
        print(Colors.BLUE + Colors.BOLD + "Bot Terminated" + Colors.END)

    def __init__(self):
        """
        Constructor of the MangoPi class that will prepare the bot will necessary variables, MongoClient, Intents, and
        also self call the run method to run the bot.

        Raises
        ------
        ConnectionRefusedError
            if bot failed to connect to MongoDB
        ValueError
            if bot token is an empty string
        """
        self.last_dc = None
        self.ignore_check = offline
        self._first_ready = True
        self._separator = "---------------------------------------------------------"

        data = KeyReader()

        try:
            # code reference:
            # https://stackoverflow.com/questions/30539183/how-do-you-check-if-the-client-for-a-mongodb-instance-is-valid
            self.mongo = MongoClient(data.db_address)[data.cluster]
            self.mongo.list_collection_names()
        except errors.ServerSelectionTimeoutError:
            raise ConnectionRefusedError("Can not connect to the specified MongoDB")

        self.default_prefix = data.prefix
        self.loaded_cogs = {}
        self.unloaded_cogs = {}

        intents = discord.Intents(
            guilds=True,
            members=True,
            bans=True,
            emojis=True,
            voice_states=True,
            dm_messages=True,
            dm_reactions=True,
            guild_messages=True,
            guild_reactions=True,
            messages=True,
            message_content=True,
            # invites=True,
        )

        super().__init__(self, help_command=CustomHelpCommand(), prefix=commands.when_mentioned_or(data.prefix),
                         intents=intents)

        self.app_info = None
        self.data = None

        self.dc_report = False

        if data.bot_token == "":
            raise ValueError("No bot token given")

        print("=========================================================\n"
              f"Now Starting Bot\t|\t{platform.system()}\n{self._separator}")

        self.run(data.bot_token)

    async def _load_all_cogs(self, location: str = './Cogs', note: str = 'Cogs'):
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
                    await self._load_all_cogs(new_location, new_note)

            for i in files:
                if i.endswith(".py") and not i.startswith("!") and i.replace(".py", "") not in self.loaded_cogs.keys():
                    element = i.replace('.py', '')
                    temp = f"{note}.{element}"

                    try:
                        await self.load_extension(temp)
                        self.loaded_cogs[element] = temp
                    except commands.NoEntryPointError:
                        print(f"{Colors.FAIL}failed to load, missing setup function{Colors.FAIL}")
                    except Exception:
                        self.unloaded_cogs[element] = temp
                        print(f"{Colors.FAIL}{location}/{i} Cog has failed to load with error:{Colors.END}")
                        traceback.print_exc()
                        # traceback.format_exc()

    async def on_ready(self):
        """
        Async method that replaces commands.Bot's on_ready. Calls _load_all_cogs method along with outputting info onto
        console when the bot is ready and connected to discord.
        """
        if self._first_ready:
            self.app_info = await self.application_info()
            self.data = BotData(self)

            print(f"Attempting to load all Cogs\n{self._separator}")
            await self._load_all_cogs()

            print("=========================================================\n"
                  "\t\tSuccessfully logged into Discord\n"
                  "*********************************************************\n"
                  f"Bot:\t| \t{self.user.name}\t({self.user.id})\n"
                  f"Owner:\t| \t{self.app_info.owner}\t({self.app_info.owner.id})\n"
                  "*********************************************************\n"
                  "\t\tInitialization complete, ready to go\n"
                  "=========================================================\n")

            self._first_ready = False

            for i in self.data.get_report_channels(common=True):
                await i.send("I am ready! 👌")

    async def on_resumed(self):
        """
        Async method that replace the commands.Bot's on_resumed that will send disconnect and reconnect time details
        onto an admin discord channel if dc_report is true.
        """
        now = datetime.datetime.utcnow()
        print(f"{self._separator}\n\tBot Session Resumed\n{self._separator}")

        if (not self.last_dc) or (not self.dc_report):
            return

        targets = self.data.get_report_channels(common=True)

        embed = discord.Embed(title="Bot Session Resumed", colour=0x1dd1a1, timestamp=now)
        embed.set_footer(text="Resumed ")
        embed.add_field(inline=False, name="Disconnect Time",
                        value=self.last_dc.strftime("UTC Time:\n`%B %#d, %Y`\n%I:%M:%S %p"))
        embed.add_field(name="Resume Time", value=now.strftime("UTC Time:\n`%B %#d, %Y`\n%I:%M:%S %p"))

        for i in targets:
            await i.send(embed=embed)

        self.last_dc = None

    async def on_connect(self):
        """
        Async event method that overrides on_connect to print out a message onto console
        """
        print(f"\tConnected to Discord\n{self._separator}")

    async def on_disconnect(self):
        """
        Async event method that overrides on_disconnect to print out a message onto console regarding the disconnect
        """
        self.last_dc = datetime.datetime.utcnow()
        print(f"{self._separator}\n\tDisconnected from Discord\n{self._separator}")

    async def on_error(self, event_method: str, *args, **kwargs):
        """
        Async method that overrides commands.Bot's error event handler. This will attempt to convert error into string
        to send over discord admin channels.

        https://discordpy.readthedocs.io/en/stable/api.html?highlight=on_error#discord.on_error

        Parameters
        ----------
        event_method : str
            The name of the event that raised the exception.
        args
            The positional arguments for the event that raised the exception.
        kwargs
            The keyword arguments for the event that raised the exception.
        """
        safe = ("on_command_error", "on_error", "on_disconnect")
        if event_method in safe:
            return

        targets = self.data.get_report_channels(error=True)
        mes = split_string(f"{traceback.format_exc()}", 1900)
        count = 1
        for i in targets:
            await i.send(f"An error has occurred in {event_method}")
            for k in mes:
                await i.send(f"Error Traceback Page **{count}**:\n```py\n{k}\n```")
                count += 1

        # the default error handling from client
        print('Ignoring exception in {}'.format(event_method), file=sys.stderr)
        traceback.print_exc()

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
        if isinstance(error, discord.Forbidden):
            return ctx.reply("Missing permission to do so", delete_after=10)

        print(f"{Colors.WARNING}{ctx.channel} > {ctx.author} : {ctx.message.content}{Colors.END}")

        targets = self.data.get_report_channels(error=True)

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
                    await i.send(f"Error Traceback Page **{count}**:\n```py\n{k}\n```")
                    count += 1

        # https://github.com/Rapptz/discord.py/blob/master/discord/ext/commands/bot.py
        print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        await ctx.message.add_reaction(emoji='⚠')
