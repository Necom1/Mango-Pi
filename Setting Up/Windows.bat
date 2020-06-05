@echo off
py -3 -m pip install -U discord.py[voice]
py -3 -m pip install -U dnspython
py -3 -m pip install -U pytz
py -3 -m pip install -U requests
py -3 -m pip install -U pymongo

echo. & echo. & echo Done! & echo.
pause