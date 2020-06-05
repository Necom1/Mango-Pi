if [[ "$OSTYPE" == "Linux" ]]; then
  var="python3 -m pip install -U"
else
  var="py -m pip install -U"
fi

echo "$OSTYPE"
$var discord.py[voice]
$var dnspython
$var pytz
$var requests
$var pymongo
