import re
import asyncio
import datetime
from abc import abstractmethod


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
    process : classmethod
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

    async def terminate(self):
        """
        Method of DelayedTask class that cancels the current running task if any.

        Raises
        ------
        asyncio.InvalidStateError
            there is not current on going task
        """
        if not self.process:
            raise asyncio.InvalidStateError("No process is running")
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
