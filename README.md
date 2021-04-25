# Mango Pi
[![](https://img.shields.io/badge/MangoPi-Invite-7289DA)](https://discord.com/oauth2/authorize?client_id=594781459001376768&scope=bot&permissions=1543892182)
[![](https://img.shields.io/badge/License-MIT-00cec9)](https://choosealicense.com/licenses/mit/)

Moderation Discord bot made with Discord.py and MongoDB.

---
### Software Requirements
[![](https://img.shields.io/badge/Python-3.5_|_3.6_|_3.7_|_3.8-4B8BBE)](https://www.python.org/downloads/release/python-389/)
[![](https://img.shields.io/badge/MongoDB-Server-589636)](https://www.mongodb.com/try/download/community)
### Python Module Requirements
* Discord.py
* PyMongo
* requests
* pytz

---
### Insturctions
1. Be sure all software requirements are fulfilled
    1. If you wish to run the bot on your local machine, then you will need to install MongoDB Community edition.
    2, If you already have a MongoDB server working else where, just simply edit `Bot Settings/keys.json` on "DB-address"
2. Check out Bot Settings/keys.json and edit the file as you see fit
    1. "token": followed by your bot token in parentheses
    2. "prefix": followed by your default prefix of choice for the bot in parentheses
    3. "DB-address": followed by your MongoDB access URL in parentheses
        1. default for MongoDB localhost is `"mongodb://localhost:27017/"`
    4. "DB-cluster": followed by MongoDB cluster of choice in parentheses
3. Run the bot either by double click or by console command `py Main.py`
    1. it is possible to run Main.py right after software requirement is fulfilled, however, it is recommended to fulfill the Module requirement beforehand as well
    2. You may encounter error after bot termination via `Ctrl + C`, however, it is safe to ignore that error (it should say something similar to `RunTimeError: Event loop is closed`)
---

## License
[MIT](https://choosealicense.com/licenses/mit/)
