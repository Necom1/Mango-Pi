import sys
import time
import subprocess


# References:
# https://www.youtube.com/playlist?list=PLW3GfRiBCHOiEkjvQj0uaUB1Q-RckYnj9
# https://www.youtube.com/playlist?list=PLpbRB6ke-VkvP1W2d_nLa1Ott3KrDx2aN

# Resources:
# https://flatuicolors.com/
# https://discordpy.readthedocs.io/

try:
    import pytz
    import requests
    import discord
    import pymongo
    import wavelink
    import yaml
except ImportError:
    print("Missing installation detected, will now attempt to manually install libraries")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

try:
    from Components.MangoPi import MangoPi

    laval = subprocess.Popen(['java', '-jar', 'Lavalink.jar'])
    time.sleep(10)
    MangoPi()
    # clean up subprocess
    laval.kill()
except ConnectionRefusedError:
    print("Bot has failed to connect to the specified MongoDB")
    print("- Go into the Bot Settings Folder and check keys.json and see if there is any spelling error")
    print("- Use MongoCompass to check if the specified MongoDB server is online")
    exit(1)
except ValueError:
    print("No bot token given, please check ./Bot Settings/keys.json and make sure you put in your bot token")
    exit(2)
