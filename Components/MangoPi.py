import os
import json
import random
import discord
import datetime
import platform
import traceback
from typing import Union
from pymongo import MongoClient
from discord.ext import commands
from Components.KeyReader import KeyReader
from Components.HelpMenu import CustomHelpCommand
from Components.PrintColor import PrintColors as Colors


status_translator = {"online": discord.Status.online, "idle": discord.Status.idle,
                     "dnd": discord.Status.dnd, "invisible": discord.Status.invisible}

activity_translator = {"watch": discord.ActivityType.watching, "play": discord.ActivityType.playing,
                       "listen": discord.ActivityType.listening, "stream": discord.ActivityType.streaming}


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


def flip_dict(original: dict):
    # https://stackoverflow.com/questions/1031851/how-do-i-exchange-keys-with-values-in-a-dictionary
    rev = dict((v, k) for k, v in original.items())
    return rev


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

        super().__init__(self, help_command=CustomHelpCommand(), prefix=commands.when_mentioned_or(data.prefix))

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
        # Code Reference: From Commando950#0251 (119533809338155010) > https://github.com/Commando950
        safe = [commands.CommandNotFound,
                commands.MissingPermissions,
                commands.BadArgument,
                commands.MissingPermissions,
                commands.CheckFailure,
                commands.errors.MissingRequiredArgument]
        if isinstance(error, tuple(safe)):
            return
        print(f"{Colors.WARNING}{ctx.channel} > {ctx.author} : {ctx.message.content}{Colors.END}")
        raise error


class BotData:

    def __init__(self, bot: MangoPi, file_name: str = "Bot Settings/data.json"):
        self.bot = bot
        self._in_use = False
        self.file_location = file_name

        self.rrp = [False, False, True, 10]
        self.staff = []
        self.activities = []
        self.status = [True, "idle", "watch", "the ocean wave!"]
        self.console_channels = []
        self.console_dm = []

        try:
            with open(f'./{file_name}') as file:
                self._data = json.load(file)

            if not all(key in self._data for key in ("activities", "status", "rrp_setting", "console", "staff")):
                raise json.decoder.JSONDecodeError

            self._data["owner"] = bot.app_info.owner.id
            self.staff = self._data["staff"]
            self.status = self._data["status"]
            self.rrp = self._data["rrp_setting"]
            self.activities = self._data["activities"]
            self.console_dm = self._data["console"]["dm"]
            self.console_channels = self._data["console"]["channel"]

        except (FileNotFoundError, json.decoder.JSONDecodeError):
            self._data = {"owner": bot.app_info.owner.id,
                          "staff": self.staff,
                          "activities": self.activities,
                          "status": self.status,
                          "rrp_setting": self.rrp,
                          "console": {"channel": self.console_channels, "dm": self.console_dm}}
            self.save()

    def save(self):
        """
        Method that writes to the data json file with the current data information.

        Raises
        ------
        RunTimeError
            if the method is currently in use
        """
        if self._in_use:
            raise RuntimeError('Currently in use')
        self._in_use = True
        with open(f'./{self.file_location}', 'w') as out:
            json.dump(self._data, out)
        self._in_use = False

    def add_staff(self, user: int):
        """
        Method that will attempt to add the specified ID to the administrator list.

        Parameters
        ----------
        user : int
            Discord ID of the user to add to the admin list

        Returns
        -------
        str
            Special condition message such as user already an admin or you are trying to add the owner.
        """
        if user in self.staff:
            return 'That user is already an admin'
        if user == self._data["owner"]:
            return 'You are the owner...'

        self.staff.append(user)

        try:
            self.save()
        except RuntimeError:
            self.staff.remove(user)
            return 'System busy, please try again later'

    def remove_staff(self, user: int):
        """
        Method that will attempt remove a specific ID from the administrator list.

        Parameters
        ----------
        user : int
            User ID of the admin to remove from bot's admin list

        Returns
        -------
        str
            Special condition message such as user not an admin or you are trying to remove the owner.
        """
        if user == self._data['owner']:
            return "No can't do master"
        if user not in self.staff:
            return 'That user is not an admin'
        self.staff.remove(user)

        try:
            self.save()
        except RuntimeError:
            self.staff.append(user)
            return 'System busy, please try again later'

    def staff_check(self, data: Union[commands.Context, int]):
        """
        Method that checks whether or not the author is part of the bot admin list.

        Parameters
        ----------
        data : Union[commands.Context, int]
            pass in context to scan for author

        Returns
        -------
        bool
            Whether or not the author is part of the bot administration
        """
        data = data if isinstance(data, int) else data.author.id

        return (data == self._data['owner']) or (data in self.staff)

    def is_in_console(self, item: int):
        return (item in self.console_dm) or (item in self.console_channels)

    def add_console(self, item: Union[discord.TextChannel, discord.User, discord.Member]):
        kind = 'channel' if isinstance(item, discord.TextChannel) else 'dm'
        if not self.is_in_console(item.id):
            self._data['console'][kind].append(item.id)
        else:
            raise ValueError(f"{item.id} is already inside console list")

    def remove_console(self, item: Union[discord.TextChannel, discord.User, discord.Member, int]):
        if isinstance(item, int):
            in_dm = item in self.console_dm
            in_channels = item in self.console_channels
            if in_dm:
                self.console_dm.remove(item)
            if in_channels:
                self.console_channels.remove(item)
            if not (in_dm or in_channels):
                raise ValueError(f"{item} not found within console list")

        kind = 'channel' if isinstance(item, discord.TextChannel) else 'dm'
        if self.is_in_console(item.id):
            self._data['console'][kind].remove(item.id)
        else:
            raise ValueError(f"{item.id} not found within console list")

    @property
    def default_status(self):
        if self.status[0]:
            temp = self._data["status"][1]
            return None if temp == "" else status_translator[temp]

    @default_status.setter
    def default_status(self, value: Union[str, discord.Status]):
        if isinstance(value, str) and value in status_translator.keys():
            self.status[1] = value
        elif isinstance(value, discord.Status) and value in status_translator.values():
            rev = flip_dict(status_translator)
            self.status[1] = rev[value]
        else:
            raise TypeError("Unknown status value")

    @property
    def default_activity(self):
        if self.status[0]:
            temp1 = self._data["status"][2]
            temp2 = self._data["status"][3]

            if temp1 == "":
                temp1 = "play"

            return discord.Activity(name=temp2, type=activity_translator[temp1])
