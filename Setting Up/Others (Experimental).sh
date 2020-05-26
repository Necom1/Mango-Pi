if [[ "$OSTYPE" == "WINDOWS" ]]; then
	py -3 -m pip install -U discord.py[voice]
	py -3 -m pip install -U dnspython
	py -3 -m pip install -U pytz
	py -3 -m pip install -U requests
	py -3 -m pip install -U pymongo
else
	python3 -m pip install -U discord.py[voice]
	python3 -m pip install -U dnspython
	python3 -m pip install -U pytz
	python3 -m pip install -U requests
	python3 -m pip install -U pymongo
