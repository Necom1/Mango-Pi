import re
import typing
import discord
import unicodedata


class Detector:
    """
    Class Detector containing Scanner information and function for a server.

    Attributes
    ----------
    guild: int
        server ID for the scanner
    name: str
        name of the scanner
    words: list
        list of string of unacceptable words
    delete: bool
        whether or not scanner should delete the problematic message
    warn: bool
        whether or not scanner should warn the author of the problematic message
    active: bool
        whether or not the scanner is active and should do any action
    channels: list
        list of IDs for the channels to ignore
    users: list
        list of IDs for the users to ignore
    roles: list
        list of IDs for the role to ignore
    """

    def __init__(self, package: dict):
        """
        Constructor for Detector class

        Parameters
        ----------
        package: dict
            pass in data from MongoDB
        """
        self.guild = package["guild"]
        self.name = package["name"]
        self.words = package["words"]
        self.words.sort()
        self.delete = package["delete"]
        self.warn = package["warn"]
        self.active = package["active"]
        self.channels = package["channels"]
        self.users = package["users"]
        self.roles = package["roles"]

    def __contains__(self, target: typing.Union[discord.Member, discord.User, discord.TextChannel, discord.Role,
                                                str, int]):
        """
        Method that works with "in" to see if the passed in item is stored within this class.

        Parameters
        ----------
        target: typing.Union[discord.Member, discord.User, discord.TextChannel, discord.Role, str, int]
            the acceptable passed in items to check

        Returns
        -------
        bool
            whether or not the passed in information are stored within the class
        """
        if isinstance(target, (discord.Member, discord.User)):
            return target.id in self.users
        if isinstance(target, discord.Role):
            return target.id in self.roles
        if isinstance(target, discord.TextChannel):
            return target.id in self.channels
        if isinstance(target, str):
            return target in self.words
        return target in self.users or target in self.channels or target in self.roles

    def scan(self, target: typing.Union[discord.Message, str], author: typing.Union[discord.Member, discord.User]):
        """
        Method that takes in a string and scans it through the word list and returns list of matching words as result

        Parameters
        ----------
        target: typing.Union[discord.Message, str]
            the string or message to be scanned through the word list
        author: typing.Union[discord.Member, discord.User]
            member with associated with the passed in target

        Returns
        -------
        list
            return list of matching words or None
        """
        if not self.active:
            return

        if author.id in self.users:
            return

        if isinstance(target, discord.Message):
            if target.channel.id in self.channels:
                return
            target = target.content

        if isinstance(author, discord.Member):
            for i in author.roles:
                if i.id in self.roles:
                    return

        ret = []

        # code from (Jack)Tewi#8723 and Commando950#0251
        target = target.replace("||", "")
        temp = str(unicodedata.normalize('NFKD', target).encode('ascii', 'ignore')).lower()
        # https://stackoverflow.com/questions/4128332/re-findall-additional-criteria
        # https://stackoverflow.com/questions/14198497/remove-char-at-specific-index-python
        # https://stackoverflow.com/questions/1798465/python-remove-last-3-characters-of-a-string
        analyze = re.findall(r"[\w']+", (temp[:0]) + temp[2:])
        f = len(analyze) - 1
        analyze[f] = analyze[f][:-1]

        for i in analyze:
            if i in self.words:
                ret.append(i)

        return ret if len(ret) != 0 else None
