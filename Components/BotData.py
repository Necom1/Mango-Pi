import random
import discord
from typing import Union
from discord.ext import commands, tasks


status_translator = {"online": discord.Status.online, "idle": discord.Status.idle,
                     "dnd": discord.Status.dnd, "invisible": discord.Status.invisible}

activity_translator = {"watch": discord.ActivityType.watching, "play": discord.ActivityType.playing,
                       "listen": discord.ActivityType.listening, "stream": discord.ActivityType.streaming}


def flip_dict(original: dict):
    # code source: https://stackoverflow.com/questions/1031851/how-do-i-exchange-keys-with-values-in-a-dictionary
    rev = dict((v, k) for k, v in original.items())
    return rev


class BotData:
    """
    Class BotData that holds status and activity related data / functions; log report data; bot staff data

    Attributes
    ----------
    bot: MangoPi
        bot reference
    owner: int
        bot owner discord ID
    _db: dict
        private dictionary holding references to all necessary MongoDB collections
    _data: dict
        private dictionary holding all the class data
    """

    def __init__(self, bot):
        """
        Constructor for BotData class

        Parameters
        ----------
        bot: MangoPi
            pass in bot reference for bot attribute
        """
        self.bot = bot
        self.owner = bot.app_info.owner.id
        self._db = {
            "staff": bot.mongo["staff"],
            "activities": bot.mongo["bot_activities"],
            "error": bot.mongo["error_report"],
            "settings": bot.mongo["bot_settings"]
        }

        self._data = {
            "staff": [],
            "activities": [],
            "console": {"channel": [], "dm": []},
            "status": ["idle", "play", "*trumpet noises*"],
            "rsa": [False, False, False, True, 10]
        }

        # status: [custom status, stat, act. type, activity]
        # rsa: [power, status, act. type, activity, timer]

        for i in self._db["staff"].find():
            self._data["staff"].append(i["_id"])

        for i in self._db["activities"].find():
            self._data["activities"].append(i["activity"])

        for i in self._db["error"].find():
            if i["dm"]:
                self._data["console"]["dm"].append(i["_id"])
            else:
                self._data["console"]["channel"].append(i["_id"])

        index = 0
        for i in ("status", "rsa"):
            temp = self._db["settings"].find_one({"_id": index})
            if not temp:
                self._db["settings"].insert_one({"_id": index, "data": self._data[i]})
            else:
                self._data[i] = temp["data"]
            index += 1

        self.rsa_process.change_interval(seconds=self.rsa[4])
        if self.rsa[0]:
            self.rsa_process.start()

    @property
    def staff(self):
        """
        Function that returns array of staff IDs

        Returns
        -------
        list
            bot staff IDs
        """
        return self._data["staff"]

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
        if user in self._data["staff"]:
            return 'That user is already a bot staff'
        if user == self.owner:
            return 'You are the owner...'

        self._data["staff"].append(user)
        self._db["staff"].insert_one({"_id": user})

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
        if user not in self._data["staff"]:
            if user == self.owner:
                return "No can't do master"
            return 'That user is not a bot staff'
        else:
            self._data["staff"].remove(user)

        self._db["staff"].delete_one({"_id": user})

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

        return (data == self.owner) or (data in self._data["staff"])

    def is_in_console(self, item: int):
        """
        Function that checks whether or not an item is in console data

        Parameters
        ----------
        item: int
            ID to check

        Returns
        -------
        bool
            whether or not the passed in item is in console report data
        """
        return (item in self._data["console"]["dm"]) or (item in self._data["console"]["channel"])

    def add_console(self, item: Union[discord.TextChannel, discord.User, discord.Member]):
        """
        Method to add a text channel or discord user into the console report data

        Parameters
        ----------
        item: Union[discord.TextChannel, discord.User, discord.Member]
            discord data with ID, text channel or user type to add into console report data

        Raises
        ------
        ValueError
            if the item is already inside the console report
        """
        kind = 'channel' if isinstance(item, discord.TextChannel) else 'dm'
        if not self.is_in_console(item.id):
            self._data['console'][kind].append(item.id)
        else:
            raise ValueError(f"{item.id} is already inside console list")
        self._db["error"].insert_one({"_id": item.id, "dm": kind == "dm"})

    def remove_console(self, item: Union[discord.TextChannel, discord.User, discord.Member, int]):
        """
        Method to remove a text channel or discord user from the console report data

        Parameters
        ----------
        item: Union[discord.TextChannel, discord.User, discord.Member]
            discord data with ID, text channel or user type to remove from console report data

        Raises
        ------
        ValueError
            if the item is not found inside the console report
        """
        if not isinstance(item, int):
            item = item.id

        if not self.is_in_console(item):
            raise ValueError(f"{item} not found within console list")
        else:
            self._db["error"].delete_one({"_id": item})

    def settings_db_update(self, update: str):
        """
        Method to update MongoDB based on provided string to update either status or rsa

        Parameters
        ----------
        update: str
            what mongoDB collection to update
        """
        translate = {"status": 0, "rsa": 1}
        try:
            mode = translate[update]
        except KeyError:
            return "Unknown parameter"
        self._db["settings"].update_one({"_id": mode}, {"$set": {"data": self._data[update]}})
        self.rsa_process.change_interval(seconds=self.rsa[4])

    def add_activity(self, item: str):
        """
        Method to add activity into the RSA data

        Parameters
        ----------
        item: str
            activity to add
        """
        data = self.activities
        data.append(item)
        self._db["activities"].insert_one({"activity": item})

    def remove_activity(self, item: str):
        """
        Method to remove activity from the RSA data

        Parameters
        ----------
        item: str
            activity to remove
        """
        data = self.activities
        data.remove(item)
        self._db["activities"].delete_one({"activity": item})

    @property
    def log_report_channels(self):
        """
        property that returns all log report channel IDs stored inside the bot

        Returns
        -------
        dict
            dictionary storing IDs that dictates channel type by key of "dm" or "channel"
        """
        return self._data["console"]

    @property
    def activities(self):
        """
        property that returns RSA activities data

        Returns
        -------
        list
            RSA activities
        """
        return self._data["activities"]

    @property
    def rsa(self):
        """
        Method property to return RSA boolean and integer data array

        Returns
        -------
        list
            RSA boolean and integer data array
        """
        return self._data["rsa"]

    @property
    def status(self):
        """
        property that returns status data

        Returns
        -------
        list
            string list of status data
        """
        return self._data["status"]

    @property
    def default_status(self):
        """
        property that returns default status for the bot

        Returns
        -------
        discord.Status
            default bot discord status
        """
        temp = self.status[0]
        return status_translator[temp]

    @property
    def default_activity(self):
        """
        property that returns default activity for the bot

        Returns
        -------
        discord.Activity
            default bot discord activity
        """
        temp1 = self.status[1]
        temp2 = self.status[2]

        return discord.Activity(name=temp2, type=activity_translator[temp1]) if temp1 != "" else None

    async def change_to_default_activity(self):
        """
        A method to change the bot status and activity with data from BotData
        """
        status = self.default_status
        activity = self.default_activity

        await self.bot.change_presence(status=status, activity=activity)

    @tasks.loop(seconds=10)
    async def rsa_process(self):
        """
        RSA task async method that is responsible for status and activity change after set intervals
        """
        discord_status = (discord.Status.online, discord.Status.idle, discord.Status.dnd)

        if self.status[0] != "invisible" and self.rsa[0]:
            stat = random.choice(discord_status) if self.rsa[1] else self.default_status
            ac = discord.Activity(
                name=random.choice(self.activities) if len(self.activities) > 0 and self.rsa[3] else self.status[2],
                type=random.choice(tuple(activity_translator.values()))
                if self.rsa[2] else activity_translator[self.status[1]]
            )
            await self.bot.change_presence(status=stat, activity=ac)
