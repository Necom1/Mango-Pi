import discord


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


def embed_message(message: discord.Message, jump: bool = False):
    """
    Method that will attempt to turn the passed in discord Message in embed (embeds if there is attachment)

    Parameters
    ----------
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
        description=message.content,
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
