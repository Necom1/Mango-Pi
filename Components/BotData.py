import json
import discord
from typing import Union
from discord.ext import commands


status_translator = {"online": discord.Status.online, "idle": discord.Status.idle,
                     "dnd": discord.Status.dnd, "invisible": discord.Status.invisible}

activity_translator = {"watch": discord.ActivityType.watching, "play": discord.ActivityType.playing,
                       "listen": discord.ActivityType.listening, "stream": discord.ActivityType.streaming}


def flip_dict(original: dict):
    # https://stackoverflow.com/questions/1031851/how-do-i-exchange-keys-with-values-in-a-dictionary
    rev = dict((v, k) for k, v in original.items())
    return rev


class BotData:

    def __init__(self, bot, file_name: str = "Bot Settings/data.json"):
        self.bot = bot
        self._in_use = False
        self.file_location = file_name

        self.rsa = [False, False, True, 10]
        self.staff = []
        self.activities = []
        self.status = [True, "idle", "watch", "the ocean wave!"]
        self.console_channels = []
        self.console_dm = []

        try:
            with open(f'./{file_name}') as file:
                self._data = json.load(file)

            if not all(key in self._data for key in ("activities", "status", "rsa_setting", "console", "staff")):
                raise json.decoder.JSONDecodeError

            self._data["owner"] = bot.app_info.owner.id
            self.staff = self._data["staff"]
            self.status = self._data["status"]
            self.rsa = self._data["rsa_setting"]
            self.activities = self._data["activities"]
            self.console_dm = self._data["console"]["dm"]
            self.console_channels = self._data["console"]["channel"]

        except (FileNotFoundError, json.decoder.JSONDecodeError):
            self._data = {"owner": bot.app_info.owner.id,
                          "staff": self.staff,
                          "activities": self.activities,
                          "status": self.status,
                          "rsa_setting": self.rsa,
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

    async def change_to_default_activity(self):
        """
        A method to change the bot status and activity with data from BotData
        """
        status = self.bot.data.default_status
        activity = self.bot.data.default_activity

        await self.bot.change_presence(status=status, activity=activity)
