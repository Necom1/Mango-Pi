import os
import json
import typing
import discord
import platform
import traceback
from pymongo import MongoClient
from discord.ext import commands


class Admins:
    """
    Class stores and manage the owner and bot administrators.

    Attributes
    ----------
    inUse : bool
        Whether or not bot-commanders.json file is currently being read/write to
    data : dict
        Dictionary that stores the bot master's ID and it's administrators
    """
    def __init__(self):
        self.inUse = False
        try:
            with open(f'./bot-commanders.json') as file:
                self.data = json.load(file)
                self.data['owner'] = bot.app_info.owner.id
        except FileNotFoundError or json.decoder.JSONDecodeError:
            self.data = {'owner': bot.app_info.owner.id, 'admins': []}
            self.update()

    def update(self):
        """
        Method that writes to bot-commanders.json with the current data information.

        Returns
        -------
        None

        Raises
        ------
        RunTimeError
            if the method is currently being called
        """
        if self.inUse:
            raise RuntimeError('Currently in use')
        self.inUse = True
        with open(f'./bot-commanders.json', 'w') as out:
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

# References:
# https://www.youtube.com/playlist?list=PLW3GfRiBCHOiEkjvQj0uaUB1Q-RckYnj9
# https://www.youtube.com/playlist?list=PLpbRB6ke-VkvP1W2d_nLa1Ott3KrDx2aN

# Resources:
# https://flatuicolors.com/
# https://discordpy.readthedocs.io/


with open('./bot-keys.json') as f:
    keys = json.load(f)

token = keys['token']
default_prefix = keys['prefix']
bot = commands.Bot(command_prefix=commands.when_mentioned_or(default_prefix))

bot.mongo = MongoClient(keys['DB-address'])[keys['DB-cluster']]
bot.loaded_cogs = {}
bot.unloaded_cogs = {}


def split_string(line: str, n: int):
    """
    Function that will split the given string into specified length and append it to array.

    Parameters
    ----------
    line : str
        the string to split
    n : int
        max length for the string

    Returns
    -------
    list
        list of the split string
    """
    # code from: https://stackoverflow.com/questions/9475241/split-string-every-nth-character
    return [line[i:i + n] for i in range(0, len(line), n)]


@bot.event
async def on_ready():
    """
    Bot event to be called when the bot is ready. This will finish bot setup and print out bot info.

    Returns
    -------
    None
    """
    print("=========================================================\n"
          "Now Starting Bot\n"
          "---------------------------------------------------------\n"
          "Attempting to load all Cogs\n"
          "---------------------------------------------------------")
    load_all_cog()
    bot.defaultPre = default_prefix
    bot.app_info = await bot.application_info()
    bot.admins = Admins()
    bot.split_string_tool = split_string
    print(f"=========================================================\n"
          f"Successfully logged into Discord\n"
          f"*********************************************************\n"
          f"Bot:\t\t\t| \t{bot.user.name}\t({bot.user.id})\n"
          f"Owner:\t\t\t| \t{bot.app_info.owner}\t({bot.app_info.owner.id})\n"
          f"Platform OS:\t|\t{platform.system()}\n"
          f"*********************************************************\n"
          "\t\t\t\tInitialization complete\n"
          f"=========================================================\n")


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    """
    A function that will be called when bot encounters a error.

    Parameters
    ----------
    ctx : commands.Context
        passing in the error context
    error : Exception
        the error

    Returns
    -------
    None

    Raises
    ------
    commands.errors
        when error that isn't caught
    """
    # Send appropriate error message on command error
    # Code Reference: From Commando950#0251 (119533809338155010) > https://gitlab.com/Commando950
    safe = [commands.CommandNotFound, commands.MissingPermissions, commands.BadArgument, commands.MissingPermissions,
            commands.CheckFailure]
    if isinstance(error, tuple(safe)):
        return
    raise error


def load_all_cog(location: str = './cogs', note: str = 'cogs'):
    """
    A function that attempt to load cogs within that directory.

    Parameters
    ----------
    location : str
        the directory to scan
    note : str
        String necessary for loading cog according to location

    Returns
    -------
    None
    """
    # load all the Cogs inside that directory
    for i in os.listdir(location):
        if i.endswith(".py") and not i.startswith("!") and i not in bot.loaded_cogs.keys():
            element = i.replace('.py', '')
            temp = f"{note}.{element}"
            try:
                bot.load_extension(temp)
                bot.loaded_cogs.update({element: temp})
            except commands.NoEntryPointError:
                print(f"{i} failed to load, missing setup function")
            except Exception as e:
                print(f"{i} failed to load:")
                bot.unloaded_cogs.update({element: temp})
                raise e

    # Scan sub-directories for potential Cogs
    for root, dirs, files in os.walk(location):
        for i in dirs:
            if not i.startswith('__'):
                new_location = location + f"/{i}"
                new_note = note + f".{i}"
                load_all_cog(new_location, new_note)


bot.run(token)
