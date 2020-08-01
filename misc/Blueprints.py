import re
import json
import asyncio
import datetime
from abc import abstractmethod
from discord.ext import commands


class DelayedTask:
    """
    Class designed to be modified to execute that async task at the specified end time and perform cleanup.

    Attributes
    ----------
    end : datetime.datetime
        represents the time when the task will execute
    seconds : float
        contains how many second until end time from constructor
    loop : asyncio.get_event_loop()
        asyncio loop
    process : method
        current running process
    """

    def __init__(self, end: datetime.datetime):
        """
        Constructor for the DelayedTask class.

        Parameters
        ----------
        end : datetime.datetime
            time for the task to execute
        """
        self.end = end
        self.seconds = 0.0
        self.loop = asyncio.get_event_loop()
        self.process = None

    def begin(self):
        """
        Method of DelayedTask class that meant to be called at the start the child constructor. This method will
        create a task base on the task method and execute it at the designated time.

        Raises
        ------
        ValueError
            if the inputted execute time has already been passed
        asyncio.InvalidStateError
            if the task is already running
        """
        start = datetime.datetime.utcnow()
        if self.end > start:
            self.seconds = float((self.end - start).total_seconds())
        else:
            raise ValueError("Time has passed...")
        if self.process:
            raise asyncio.InvalidStateError("Process is already running")
        self.process = self.loop.create_task(self.task())

    async def terminate(self, ignore: bool = False):
        """
        Method of DelayedTask class that cancels the current running task if any.

        Parameters
        ----------
        ignore: bool
            whether or not ignore exception, default is false

        Raises
        ------
        asyncio.InvalidStateError
            there is not current on going task
        """
        if not self.process:
            if not ignore:
                raise asyncio.InvalidStateError("No process is running")
            else:
                return
        self.process.cancel()
        await self.on_exit()
        self.process = None

    @abstractmethod
    async def task(self):
        """
        Empty task method for begin method. Meant to be implemented and be called from begin method.
        """
        pass

    @abstractmethod
    async def on_exit(self):
        """
        Empty exit method for terminate method. Meant to be implemented and be called from terminate method.
        """
        pass

    def __del__(self):
        asyncio.get_event_loop().create_task(self.terminate(True))


class Admins:
    """
    Class stores and manage bot admin info

    Attributes
    ----------
    inUse : bool
        Whether or not bot-commanders.json file is currently being read/write to
    data : dict
        Dictionary that stores the bot master's ID and it's administrators
    file: str
        file location for the json setting file
    """

    def __init__(self, bot: commands.Bot, file_name: str = "Bot Settings/bot-commanders.json"):
        """
        Constructor for the Admins class

        Parameters
        ----------
        bot: commands.Bot
            pass in bot for checking owner
        """
        self.inUse = False
        self.file = file_name
        try:
            with open(f'./{file_name}') as file:
                self.data = json.load(file)
                self.data['owner'] = bot.app_info.owner.id
        except FileNotFoundError or json.decoder.JSONDecodeError:
            self.data = {'owner': bot.app_info.owner.id, 'admins': []}
            self.update()

    def update(self):
        """
        Method that writes to bot-commanders.json with the current data information.

        Raises
        ------
        RunTimeError
            if the method is currently being called
        """
        if self.inUse:
            raise RuntimeError('Currently in use')
        self.inUse = True
        with open(f'./{self.file}', 'w') as out:
            json.dump(self.data, out)
        self.inUse = False

    def add(self, user: int):
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
        if user in self.data['admins']:
            return 'That user is already an admin'
        if user == self.data['owner']:
            return 'You are the owner...'
        self.data['admins'].append(user)
        self.update()

    def remove(self, user: int):
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
        if user == self.data['owner']:
            return "No can't do master"
        if user not in self.data['admins']:
            return 'That user is not an admin'
        self.data['admins'].remove(user)
        self.update()

    def check(self, ctx: commands.Context):
        """
        Method that checks whether or not the author is part of the bot admin list.

        Parameters
        ----------
        ctx : commands.Context
            pass in context to scan for author

        Returns
        -------
        bool
            Whether or not the author is part of the bot administration
        """
        return (ctx.author.id == self.data['owner']) or (ctx.author.id in self.data['admins'])


def time_converter(time: str, start: datetime.datetime):
    """
    Function that will convert the formatted array of integers and start time for time calculation.

    Parameters
    ----------
    time: str
        the string of time in int followed by a letter format
    start : datetime.datetime
        starting time for the additional

    Returns
    -------
    datetime.datetime
        final calculated time from start and array

    Raises
    ------
    ValueError
        if there is issue with the input
    """
    negative = time.startswith('-')
    if negative:
        time = time[1:]

    converted = list(re.findall(r'(\d+)(\w+?)', time))
    if len(converted) == 0 or len(converted) > 5:
        raise ValueError("Improper input.")

    time = [0, 0, 0, 0, 0]
    order = ['w', 'd', 'h', 'm', 's']
    to_word = {'w': 'week', 'd': 'day', 'h': 'hour', 'm': 'minute', 's': 'second'}
    limit = [10428, 73000, 1752000, 105100000, 6307000000]
    for i in converted:
        try:
            target = order.index(i[1])
        except ValueError:
            raise ValueError(f"**{i[1]}** isn't a valid letter input")
        if time[target] != 0:
            raise ValueError("Improper input, please don't do '1m1m' or '1h2h'.")
        if int(i[0]) >= limit[target]:
            raise ValueError(f"Value too large. Please make sure it's less than {limit[target]} {to_word[i[1]]}s")
        time[target] += int(i[0])

    if negative:
        ret = start - datetime.timedelta(seconds=time[4], minutes=time[3], hours=time[2], days=time[1], weeks=time[0])
    else:
        ret = start + datetime.timedelta(seconds=time[4], minutes=time[3], hours=time[2], days=time[1], weeks=time[0])
    return ret


def range_calculator(limit: int, size: int, current: int):
    """
    Function that returns starting point, end point, and total pages based on input

    Parameters
    ----------
    limit: int
        the number of max items display on a page
    size: int
        size of the total items
    current: int
        the current "page"

    Returns
    -------
    int, int, int
        data in the order of starting point, ending point, max number of pages
    """
    total_page = (size // limit) + 1
    start = 0 if current == 1 else (limit * (current - 1))
    end = size if start + limit >= size else start + limit

    return start, end, total_page


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
    return ctx.bot.admins.check(ctx)
