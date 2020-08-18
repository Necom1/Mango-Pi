import sys
import json


class KeyReader:

    def __init__(self, location: str = "./Bot Settings/keys.json"):
        self._data = {
            "token": "",
            "prefix": "[]",
            "DB-address": "mongodb://localhost:27017/",
            "DB-cluster": "discord-bot"
        }

        try:
            with open(location) as f:
                verified = json.load(f)
                if not all(key in verified for key in ("token", "prefix", "DB-address", "DB-cluster")):
                    raise KeyError(f"Not all necessary tokens/keys is in {location} json")
        except (FileNotFoundError, json.decoder.JSONDecodeError, KeyError):
            with open(location, 'w') as out:
                json.dump(self._data, out)

            sys.exit(f"{location} file not found or is in a wrong format. "
                     f"New file has been created, please edit and try again")

        for i in ("token", "prefix", "DB-address", "DB-cluster"):
            if verified[i] == "":
                sys.exit(f"{location} error: {i} can not be empty.")

        self.location = location
        self._data = verified

    @property
    def bot_token(self):
        return self._data["token"]

    @property
    def prefix(self):
        return self._data["prefix"]

    @property
    def db_address(self):
        return self._data["DB-address"]

    @property
    def cluster(self):
        return self._data["DB-cluster"]
