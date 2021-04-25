import sys
import subprocess


# References:
# https://www.youtube.com/playlist?list=PLW3GfRiBCHOiEkjvQj0uaUB1Q-RckYnj9
# https://www.youtube.com/playlist?list=PLpbRB6ke-VkvP1W2d_nLa1Ott3KrDx2aN

# Resources:
# https://flatuicolors.com/
# https://discordpy.readthedocs.io/

checks = [
    "pytz",
    "pymongo",
    "requests",
    "discord.py[voice]"
]

try:
    import pytz
    import requests
    import discord
    import pymongo
except ImportError:
    print("Missing installation detected, will now attempt to manually install libraries")
    for i in checks:
        # code reference: https://stackoverflow.com/questions/12332975/installing-python-module-within-code
        subprocess.check_call([sys.executable, "-m", "pip", "install", i])

try:
    from Components.MangoPi import MangoPi
    MangoPi()
except ConnectionRefusedError:
    print("Bot has failed to connect to the specified MongoDB")
    print("- Go into the Bot Settings Folder and check keys.json and see if there is any spelling error")
    print("- Use MongoCompass to check if the specified MongoDB server is online")
    exit(1)
