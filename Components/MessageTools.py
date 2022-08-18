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
    embed.set_footer(text=f"User ID: {message.author.id}", icon_url=message.author.avatar.replace(size=64).url)

    if is_dm:
        embed.set_author(name=f"Received DM from {message.author.name}")
    else:
        embed.set_author(icon_url=message.guild.icon.replace(size=128).url,
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
    discord.Embed
        returns an embed with the sent message(s) result

    Raises
    ------
    ValueError
        if the provided content string is longer than 2000 characters
    """
    reply = isinstance(mode, discord.Message)
    temp = mode
    if isinstance(temp, discord.Message):
        temp = mode.channel
        if isinstance(temp, discord.DMChannel):
            temp = temp.recipient

    ret = discord.Embed(
        title="Message Sent",
        colour=0xffbe76,
        timestamp=datetime.datetime.utcnow()
    )
    ret.add_field(inline=False, name="Jump Link", value="Temporary hold")
    ret.add_field(inline=False, name=f"Destination - {temp.id}", value=temp.mention)

    send = []

    string = content if isinstance(content, str) else content.content
    if len(string) > 2000:
        raise ValueError("Provided content string is longer than 2000 characters")
    string = content_insert_emotes(bot, string)

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

    ids = []

    if len(send) == 0:
        temp = await mode.reply(string) if reply else await mode.send(string)
    else:
        temp = await mode.reply(string, embed=send[0]) if reply else await mode.send(string, embed=send[0])
    ret.set_field_at(0, name="Jump Link", value=f"[Click Me!]({temp.jump_url})", inline=False)
    ids.append(str(temp.id))

    if len(send) > 1:
        for i in range(1, len(send)):
            temp = await mode.reply(embed=send[i]) if reply else await mode.send(embed=send[i])
            ids.append(str(temp.id))

    ret.add_field(inline=False, name="Message IDs", value="\n".join(ids))

    return ret
