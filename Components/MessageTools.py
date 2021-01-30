import re
import typing
import discord
import datetime
from discord.ext.commands import Bot


def split_string(line: str, n: int):
    """
    Function that will split the given string into specified length and append it to array.

    Parameters
    ----------
    line: str
        the string to split
    n: int
        max length for the string

    Returns
    -------
    list
        list of the split string
    """
    # code from: https://stackoverflow.com/questions/9475241/split-string-every-nth-character
    return [line[i:i + n] for i in range(0, len(line), n)]


def image_check(link: str):
    """
    Function that checks the passed in link's end extension.

    Parameters
    ----------
    link: str
        the link to check for

    Returns
    -------
    bool
        whether or not the passed in link contains "image" format ending
    """
    return link.lower().endswith(('.jpg', '.png', '.jpeg', '.gif', '.webp', '.bmp', '.tiff'))


def content_insert_emotes(bot: Bot, string: str):
    """
    Method that will attempt to turn the passed in string and replace emoji sequences with the appropriate emote

    Parameters
    ----------
    bot: Bot
        pass in bot reference to find emotes
    string: str
        the string that may or may not contain emote sequences (from doing message.content)

    Returns
    -------
    str
        the new string with emotes
    """
    # some code from:
    # https://stackoverflow.com/questions/54859876/how-check-on-message-if-message-has-emoji-for-discord-py

    found = list(set(re.findall(r'<:\w*:\d*>', string)))

    for i in found:
        temp = int(i.split(':')[2].replace('>', ''))
        temp = bot.get_emoji(temp)
        if temp:
            string.replace(i, str(temp))

    return string


def embed_message(bot: Bot, message: discord.Message, jump: bool = False):
    """
    Method that will attempt to turn the passed in discord Message in embed (embeds if there is attachment)

    Parameters
    ----------
    bot: Bot
        the bot reference
    message: discord.Message
        discord message to turn into embed
    jump: bool
        whether or not to include jump link

    Returns
    -------
    list
        list of discord Embeds generated
    """
    is_dm = message.channel.type is discord.ChannelType.private

    ret = []

    embed = discord.Embed(
        description=content_insert_emotes(bot, message.content),
        colour=0xdff9fb if is_dm else message.author.color,
        timestamp=message.created_at
    )
    embed.set_footer(text=f"User ID: {message.author.id}", icon_url=message.author.avatar_url_as(size=64))

    if is_dm:
        embed.set_author(name=f"Received DM from {message.author.name}")
    else:
        embed.set_author(icon_url=message.guild.icon_url_as(size=128),
                         name=f"Message from {message.author.name} in {message.guild}")

    if jump:
        embed.add_field(name="Jump Link", value=f"[Message Location]({message.jump_url})", inline=False)

    files = message.attachments

    if len(files) == 1:
        f = files[0]
        if image_check(f.url):
            embed.set_image(url=f.url)
        else:
            embed.add_field(name="File Attachment", value=f"{f.url}")
    ret.append(embed)

    if len(files) > 1:
        count = 1
        temp = discord.Embed(
            colour=0xdff9fb if is_dm else message.author.color,
            timestamp=message.created_at,
            title="Multiple File Attachments"
        )
        for i in files:
            temp.add_field(name=f"Attachment #{count}", value=f"[File {count}] ({i.url})")
            count += 1
        ret.append(temp)

    return ret


async def send_message(bot: Bot, mode: typing.Union[discord.TextChannel, discord.User, discord.Message],
                       content: typing.Union[str, discord.Message], special_file: tuple = None):
    """
    Function that sends messages to a specified location (mode) with provided content and / or special files

    Parameters
    ----------
    bot
    mode: typing.Union[discord.TextChannel, discord.User, discord.Message]
        will either reply if mode is discord.Message or simply send to that specific location
    content: typing.Union[str, discord.Message]
        the content to send
    special_file: tuple
        tuple of discord attachments to embed

    Returns
    -------
    tuple
        returns a list with first being either channel or user ID (if mode is send in a DM), and then the messages the
        bot send

    Raises
    ------
    ValueError
        if the provided content string is longer than 2000 characters
    """
    reply = isinstance(mode, discord.Message)
    ret = []
    temp = mode
    if isinstance(temp, discord.Message):
        temp = mode.channel
        if isinstance(temp, discord.DMChannel):
            temp = temp.recipient
    ret.append(temp)

    send = []

    string = content if isinstance(content, str) else content.content
    string = content_insert_emotes(bot, string)

    if len(string) > 2000:
        raise ValueError("Provided content string is longer than 2000 characters")

    try:
        files = content.attachments if not special_file else special_file
    except AttributeError:
        # passed in is a string
        files = []

    embed = discord.Embed(
        timestamp=datetime.datetime.utcnow()
    )

    if len(files) == 1:
        f = files[0]
        if image_check(f.url):
            embed.set_image(url=f.url)
        else:
            embed.add_field(name="File Attachment", value=f"{f.url}")
        send.append(embed)

    if len(files) > 1:
        count = 1
        embed.title = "Multiple File Attachments"
        template = embed.copy()
        has_non_image = False
        for i in files:
            template.title = f"Attachment #{count} [Image]"
            if image_check(i.url):
                template.set_image(url=i.url)
                send.append(template.copy())
            else:
                has_non_image = True
                embed.add_field(name=f"Attachment #{count}", value=f"[File {count}] ({i.url})")
            count += 1
        if has_non_image:
            send.append(embed)

    if len(send) == 0:
        temp = await mode.reply(string) if reply else await mode.send(string)
        ret.append(temp.id)
    else:
        temp = await mode.reply(string, embed=send[0]) if reply else await mode.send(string, embed=send[0])
        ret.append(temp.id)
    if len(send) > 1:
        for i in range(1, len(send)):
            temp = await mode.reply(embed=send[i]) if reply else await mode.send(embed=send[i])
            ret.append(temp.id)

    return tuple(ret)
