import asyncio
import discord
import itertools
from discord.ext.commands.help import HelpCommand
from discord.ext.commands import Command, Context, Group, Cog


def process_description(description: str):
    """
    Function to cut the passed in string before \n\n if any

    Parameters
    ----------
    description: str
        the passed in string for process

    Returns
    -------
    str
        processed string
    """
    return description.rpartition('\n\n')[0] if "\n\n" in description else description


def process_command_list(original: discord.Embed, filtered: list):
    """
    Function that appends the passed in list of commands onto the provided embed

    Parameters
    ----------
    original: discord.Embed
        the embed template for append the command to as fields
    filtered: list
        list of commands

    Returns
    -------
    tuple
        list of embeds with the passed in commands
    """
    ret = [original.copy()]
    i = 0
    count = 0

    for command in filtered:
        if count % 25 == 0 and count != 0:
            ret.append(original.copy())
            i += 1

        name = command.name
        detail = str(command.short_doc)
        ret[i].add_field(name=name, value=detail.replace("\n", " "), inline=False)
        count += 1

    return tuple(ret)


class EmbedPaginator:
    """
    Class of a Paginator that stores command details as embeds

    Attributes
    ----------
    buffer: list
        list containing the commands in embed
    self.color: int
        number representing a HTML hexadecimal color for the embed
    """

    def __init__(self):
        """
        EmbedPaginator class constructor
        """
        self.buffer = []
        self.color = 0x18dcff

    def clear(self):
        """
        Method that clears the buffer
        """
        self.buffer.clear()

    def finalize(self, icon: str = None):
        """
        Method that returns the list of embeds in buffer and assign their footer with page numbers

        Parameters
        ----------
        icon: str
            the URL of the image to be shown at footer

        Returns
        -------
        list
            list of processed embeds
        """
        ret = self.buffer.copy()
        count = 1
        for i in ret:
            i.set_footer(icon_url=icon, text=f"{count} / {len(ret)} pages")
            count += 1
        return ret

    def add_commands(self, heading: str, commands: list):
        """
        Method for adding commands into buffer as embed

        Parameters
        ----------
        heading: str
            Cog name
        commands: list
            list of commands
        """
        embed = discord.Embed(colour=self.color,
                              title=f"**__{heading}__** Cog" if heading != "​No Category" else heading)

        ret = process_command_list(embed, commands)
        for i in ret:
            self.buffer.append(i)


class CustomHelpCommand(HelpCommand):
    """
    Child class of HelpCommand to help process help command request by the bot
    some of the code by Rapptz's DefaultHelpCommand

    Attributes
    ----------
    sort_commands: bool
        whether or not to sort commands
    dm_help: bool
        whether or not help command call will be redirected into private message instead
    no_category: str
        What is used for displaying commands that have no category
    paginator: EmbedPaginator
        the embed paginator for embedding commands
    checked: method
        method for checking whether or not help command is legal to be posted
    """

    def __init__(self, **options):
        """
        Constructor for CustomHelpCommand

        Parameters
        ----------
        options: dict
            different options setting for the class variables if applicable
        """
        self.sort_commands = options.pop('sort_commands', True)
        self.dm_help = options.pop('dm_help', False)
        self.no_category = options.pop('no_category', 'No Category')
        self.paginator = EmbedPaginator()
        self.checked = options.pop('ignore_check', self.ignore_check)
        super().__init__(**options)

    def get_command_signature(self, command: Command):
        """
        Method that constructs a signature from the passed in command

        Parameters
        ----------
        command: Command
            crafting signature for this command

        Returns
        -------
        str
            command signature
        """
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '/'.join(command.aliases)
            fmt = f"<{command.name}/{aliases}>"
            if parent:
                fmt = parent + ' ' + fmt
            alias = fmt
        else:
            alias = command.name if not parent else parent + ' ' + command.name

        signature = command.signature.replace("[", "(")
        signature = signature.replace("]", ")")

        return f"{self.clean_prefix}{alias} {signature}"

    def get_destination(self):
        """
        Method that returns the appropriate reply location base on if dm_help instead is True or not

        Returns
        -------
        discord.User
            if dm_help is True
        discord.Channel
            if dm_help is False
        """
        ctx = self.context
        return ctx.author if self.dm_help else ctx.channel

    async def prepare_help_command(self, ctx: Context, command: str = None):
        """
        Async method that prepares help command, usually called before anything.

        Parameters
        ----------
        ctx: Context
            pass in context for parent class method
        command: str
            argument passed in by the user
        """
        self.paginator.clear()
        await super().prepare_help_command(ctx, command)

    async def send_bot_help(self, mapping):
        """
        Async method that is to be called when user call help command without any additional parameter input. Prepares
        help menu.

        Parameters
        ----------
        mapping: Mapping[Optional[Cog], List[Command]]
            require parameter from parent class, however, not used in this case.
        """
        if self.checked():
            return

        ctx = self.context
        bot = ctx.bot

        noc = '\u200b{0.no_category}'.format(self)

        def get_category(com: Command, *, no_category: str = noc):
            cog = com.cog
            return cog.qualified_name if cog else no_category

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        to_iterate = itertools.groupby(filtered, key=get_category)

        for category, commands in to_iterate:
            commands = sorted(commands, key=lambda c: c.name) if self.sort_commands else list(commands)
            self.paginator.add_commands(category, commands)

        special = list(self.paginator.finalize(bot.user.avatar_url_as(size=64)))
        if self.context.channel.type != discord.ChannelType.private:
            await self.interactive(special)
        else:
            for i in special:
                await self.get_destination().send(embed=i)

    async def send_command_help(self, command: Command):
        """
        Async method that will send the specified command info in embed format

        Parameters
        ----------
        command: Command
            command requesting more info for
        """
        if self.checked():
            return

        signature = self.get_command_signature(command)
        description = command.help.replace("\n", " ")
        embed = discord.Embed(colour=self.paginator.color, description=description, title=signature)
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group: Group):
        """
        Async method that will send the specified command group info in embed format

        Parameters
        ----------
        group: Group
            the command group requesting more info for
        """
        if self.checked():
            return

        signature = self.get_command_signature(group)
        description = process_description(group.help)
        description = f"{description}\n\n__Sub-commands__:" if len(description) > 0 else "__Sub-commands__:"
        embed = discord.Embed(
            colour=self.paginator.color, title=signature, description=description
        )

        filtered = await self.filter_commands(group.commands, sort=self.sort_commands)
        result = process_command_list(embed, filtered)
        icon = self.context.bot.user.avatar_url_as(size=64)

        for i in range(len(result)):
            result[i].set_footer(icon_url=icon, text=f"{i + 1} / {len(result)} Pages")
            await self.get_destination().send(embed=result[i])

    async def send_cog_help(self, cog: Cog):
        """
        Async method that will send the specified Cog info in embed format

        Parameters
        ----------
        cog: Cog
            the cog requesting more info for
        """
        if self.checked():
            return

        embed = discord.Embed(
            colour=self.paginator.color, title=f"**__{cog.qualified_name}__** Cog", description="__Commands__:"
        )

        filtered = await self.filter_commands(cog.get_commands(), sort=self.sort_commands)
        result = process_command_list(embed, filtered)
        icon = self.context.bot.user.avatar_url_as(size=64)

        for i in range(len(result)):
            result[i].set_footer(icon_url=icon, text=f"{i + 1} / {len(result)} Pages")
            await self.get_destination().send(embed=result[i])

    async def interactive(self, data: list):
        """
        Async method that turns all the passed in list of embeds in a single message page navigator by reaction

        Parameters
        ----------
        data: list
            list of embeds
        """
        reacts = ['⏮', '⏪', '⏹', '⏩', '⏭', '📋', '🔢']
        info = discord.Embed(
            title="Help Command Guide",
            colour=0x16a085,
            description="<...> - mandatory input\n(...) - optional input\n"
                        "/ - separator for different options\n\n"
                        "Doing the command call after help will tell you more information about that command\n"
                        f"**Example**: ```{self.context.prefix}help ping```\n\n"
                        "|> Multi-action will require __parentheses__ around the phrase to add or remove the"
                        "desire words\n"
                        "Do note that some command will require permission to perform."
        ).set_footer(text="Information Menu, react with other reactions to exit.")

        current = 0
        ctx = self.context

        message = await self.get_destination().send(embed=data[current])
        for i in reacts:
            await message.add_reaction(emoji=i)

        def check(reaction1: discord.Reaction, user1: discord.User):
            return (reaction1.message.id == message.id) and (user1.id == ctx.author.id) \
                   and (reaction1.emoji in reacts)

        def msg_check(m: discord.Message):
            return m.channel == message.channel and m.author.id == ctx.author.id

        stop = False
        in_help = False
        not_private = message.channel.type != discord.ChannelType.private

        while not stop:
            try:
                reaction, user = await self.context.bot.wait_for('reaction_add', timeout=30, check=check)
            except asyncio.TimeoutError:
                await message.clear_reactions()
                await message.edit(content="Help menu timed out.")
                break

            change = True

            if reaction.emoji == '⏮':
                if current == 0:
                    change = False
                else:
                    current = 0
            elif reaction.emoji == '⏪':
                if not (current - 1 < 0):
                    current -= 1
                else:
                    change = False
            elif reaction.emoji == '⏹':
                await message.edit(content="Help menu paused")
                if not_private:
                    await message.clear_reactions()
                break
            elif reaction.emoji == '⏩':
                if not (current + 1 >= len(data)):
                    current += 1
                else:
                    change = False
            elif reaction.emoji == '⏭':
                if current == len(data) - 1:
                    change = False
                else:
                    current = len(data) - 1
            elif reaction.emoji == '🔢':
                await message.edit(content=f"enter the page (1 - {len(data)}) you want to jump to", embed=None)
                try:
                    msg = await ctx.bot.wait_for("message", check=msg_check)
                except asyncio.TimeoutError:
                    await message.edit(content="Response time out", embed=None)
                    await message.clear_reactions()
                    break
                try:
                    temp = int(msg.content) - 1
                    if 0 <= temp < len(data):
                        current = temp
                    else:
                        raise ValueError
                except ValueError:
                    await message.edit(content="Invalid Input", embed=None)
                    await message.clear_reactions()
                    break
                try:
                    await msg.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
            else:
                if in_help:
                    in_help = False
                else:
                    in_help = True

            if change:
                await message.edit(embed=info if in_help else data[current])
            if not_private:
                await message.remove_reaction(reaction.emoji, user)

    def ignore_check(self):
        """
        Method contain the default ignore_check for mango pi, if there is attribute error, always return true

        Returns
        -------
        bool
            whether or not the channel is not in ignore channel command list
        """
        try:
            return self.context.bot.ignore_check(self.context)
        except AttributeError:
            return True
