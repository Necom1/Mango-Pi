import os
import json
import typing
import discord
import platform
import traceback
from pymongo import MongoClient
from discord.ext import commands
from misc.Blueprints import Admins
from misc.HelpMenu import CustomHelpCommand

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
bot = commands.Bot(command_prefix=commands.when_mentioned_or(default_prefix), help_command=CustomHelpCommand())

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
    """
    print("=========================================================\n"
          "Now Starting Bot\n"
          "---------------------------------------------------------\n"
          "Attempting to load all Cogs\n"
          "---------------------------------------------------------")
    load_all_cog()
    bot.defaultPre = default_prefix
    bot.app_info = await bot.application_info()
    bot.admins = Admins(bot)
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

    Raises
    ------
    commands.errors
        when error that isn't caught
    """
    # Send appropriate error message on command error
    # Code Reference: From Commando950#0251 (119533809338155010) > https://gitlab.com/Commando950
    safe = [commands.CommandNotFound, commands.MissingPermissions, commands.BadArgument, commands.MissingPermissions,
            commands.CheckFailure, commands.errors.MissingRequiredArgument]
    if isinstance(error, tuple(safe)):
        return
    print('\033[93m' + f"{ctx.channel} > {ctx.author} : {ctx.message.content}")
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
    """
    # load all the Cogs inside that directory
    for root, dirs, files in os.walk(location):
        # Scan sub-directories for potential Cogs
        for i in dirs:
            if not i.startswith('__'):
                new_location = f"{location}/{i}"
                new_note = f"{note}.{i}"
                load_all_cog(new_location, new_note)

        for i in files:
            if i.endswith(".py") and not i.startswith("!") and i.replace(".py", "") not in bot.loaded_cogs.keys():
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


bot.run(token)
