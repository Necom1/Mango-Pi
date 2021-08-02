import typing
import discord
import asyncio
import datetime
from discord.ext import commands
from Components.MangoPi import MangoPi, is_admin
from Components.MessageTools import embed_message, send_message


def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog
    """
    bot.add_cog(ChatSystem(bot))
    print("Load Cog:\tChatSystem")


def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog
    """
    bot.remove_cog("ChatSystem")
    print("Unload Cog:\tChatSystem")


class ChatSystem(commands.Cog):
    """
    Class inherited from Commands.Cog that contains chat system commands for admins

    Attributes
    ----------
    bot: MangoPi
        bot reference
    db: MongoClient
        mongodb "chats" collection reference
    data: list
        local db copy of IDs of either user or channels that the bot should listen for
    tasks: dict
        task system stored data in format of (bot redirected msg ID: asyncio task)
    cache: dict
        cache system storing data in the format of (bot redirected msg ID: actual msg ID) for replying to those msgs
    cache2: dict
        cache system storing data in the format of (original msg ID: [lists of bot redirect msg IDs]) for updating
        redirected bot messages
    tasks2: dict
        cache system storing data in the format of (notify msg ID: [asyncio task, display message]) for cancelling
        wait_for if needed
    """

    def __init__(self, bot: MangoPi):
        """
        Constructor for ChatSystem class

        Parameters
        ----------
        bot: MangoPi
            takes in MangoPi reference
        """
        self.bot = bot
        self.db = bot.mongo["chats"]
        self.data = []
        for i in list(self.db.find({})):
            self.data.append(i['_id'])

        self.bl_db = bot.mongo["chat_blacklist"]
        self.bl_data = []
        for i in list(self.bl_db.find()):
            self.bl_data.append(i['_id'])

        self.tasks = {}
        self.cache = {}
        self.cache2 = {}
        self.tasks2 = {}

    async def cache_message(self, sent: discord.Message, message: discord.Message):
        """
        Async method that caches the bot reference message and the original message into the 2 caches and remove it
        after 120 seconds. This is mainly for tasks

        Parameters
        ----------
        sent: discord.Message
            bot redirecting / bot embed of the original message
        message: discord.Message
            original message
        """
        self.cache[sent.id] = message
        try:
            self.cache2[message.id].append(sent)
        except KeyError:
            self.cache2[message.id] = [sent]

        await asyncio.sleep(120)

        try:
            self.cache.pop(sent.id)
        except KeyError:
            pass

        try:
            self.cache2[message.id].remove(sent)
            if len(self.cache2[message.id]) < 1:
                self.cache2.pop(message.id)
        except KeyError:
            pass

        try:
            self.tasks.pop(sent.id)
        except KeyError:
            pass

    async def wait_for_message(self, msg: discord.Message, location: discord.Message, user: discord.User):
        """
        Async method that waits indefinitely for admin to enter a reply message, attach itself onto tasks2 so it can
        be cancelled in case the admin change their mind or on cache clear

        Parameters
        ----------
        msg: discord.Message
            the display message
        location: discord.Message
            reference to the original message to reply to
        user: discord.User
            the user reference that initialized this feature
        """
        def check(m: discord.Message):
            return m.author.id == user.id

        await msg.add_reaction(emoji='🛑')
        data = await self.bot.wait_for("message", check=check)
        returned = await send_message(self.bot, location, data)
        await msg.edit(content="", embed=returned)

        try:
            data = self.tasks2.pop(msg.id)
            data[0].cancel()
        except KeyError:
            pass

    @commands.command()
    @commands.check(is_admin)
    async def send(self, ctx: commands.Context,
                   destination: typing.Union[discord.DMChannel, discord.TextChannel, discord.Member, discord.User],
                   *, messages: str = ""):
        """Command to send message to the specified location as the bot"""
        if len(ctx.message.attachments) < 1 and messages == "":
            return await ctx.reply("I don't know what to send...")

        returned = await send_message(self.bot, destination, messages, ctx.message.attachments)
        await ctx.message.reply(content="", embed=returned)

    @commands.command(aliases=['msg'])
    async def message_bot_admins(self, ctx: commands.Context, *, m: str = ""):
        """Command to send a message to bot admins"""
        channel_check = isinstance(ctx.channel, discord.TextChannel)
        check_id = ctx.channel.id if channel_check else ctx.author.id

        if check_id in self.data:
            # the chat is currently being focused on, no need to send dup
            return

        if ctx.author.id in self.bl_data:
            return
        if ctx.channel.id in self.bl_data:
            return

        if len(ctx.message.attachments) < 1 and m == "":
            return await ctx.reply("W-What am I sending...?")

        original = embed_message(self.bot, ctx.message)
        destinations = self.bot.data.get_report_channels(chat=True)
        extra = f"in {ctx.channel.mention} ({ctx.channel.id})" if channel_check else \
            f"from {ctx.author.mention} ({ctx.author.id})'s DM"

        for a in original:
            for i in destinations:
                await i.send(f"**From** `message_bot_admins` command {extra}", embed=a)

        await ctx.message.add_reaction(emoji='📨')

    @commands.command()
    @commands.check(is_admin)
    async def reply(self, ctx: commands.Context,
                    destination: typing.Union[discord.DMChannel, discord.TextChannel, discord.Member, discord.User],
                    message_id: int, *, messages: str = ""):
        """Command to reply to specified message as the bot"""
        if len(ctx.message.attachments) < 1 and messages == "":
            return await ctx.reply("I don't know what to send...")

        destination = destination.dm_channel if isinstance(destination, (discord.User, discord.Member)) else destination
        msg = await destination.fetch_message(message_id)
        if not msg:
            return await ctx.reply("Can not find the specified message")

        ret = await send_message(self.bot, msg, messages, ctx.message.attachments)
        await ctx.message.reply(content="", embed=ret)

    @commands.group(aliases=['chatsystem'])
    @commands.check(is_admin)
    async def chat(self, ctx: commands.Context):
        """Group command of chat system for the bot, if not invoked with sub-command will bring up chat system data"""
        if not ctx.invoked_subcommand:
            ref = {'u': 'Users', 'c': 'Channels', 'e': 'Error'}
            results = {'u': [], 'c': [], 'e': []}

            for i in self.data:
                temp = self.bot.get_user(i)
                if not temp:
                    temp = self.bot.get_channel(i)
                    if not temp:
                        results['e'].append(i)
                    else:
                        results['c'].append(temp)
                else:
                    results['u'].append(temp)

            embed = discord.Embed(
                colour=0x00d2d3,
                timestamp=ctx.message.created_at,
                title="Chat System Data"
            )

            no = True

            for k, v in results.items():
                if len(v) > 0:
                    no = False
                    string = ""
                    for i in v:
                        string += f"{i.mention if k != 'e' else i}\n"
                    embed.add_field(inline=False, name=ref[k], value=string)

            if no:
                embed.description = "No Data So Far"

            await ctx.reply(embed=embed)

    @chat.command(aliases=['f', '+', 'add'])
    async def focus(self, ctx: commands.Context,
                    data: typing.Union[int, discord.User, discord.Member, discord.TextChannel]):
        """Add a specific channel or user DM for chat system to listen to"""
        if isinstance(data, int):
            new = self.bot.get_channel(data)
            if not new:
                new = self.bot.get_user(data)
                if not new:
                    return await ctx.reply("Can not find anything with the specified ID")
            data = new

        if data.id not in self.data:
            self.data.append(data.id)
            self.db.insert_one({"_id": data.id})
            await ctx.message.add_reaction(emoji="👌")
        else:
            await ctx.reply("ID already exist within the chat system")

    @chat.command(aliases=['u', '-', 'remove'])
    async def unfocus(self, ctx: commands.Context,
                      data: typing.Union[int, discord.User, discord.Member, discord.TextChannel]):
        """Remove a specified channel or user DM from chat system"""
        if not isinstance(data, int):
            data = data.id

        if data in self.data:
            self.data.remove(data)
            self.db.delete_one({"_id": data})
            await ctx.message.add_reaction(emoji="👌")
        else:
            await ctx.reply("Can not find the specified ID within the chat system")

    @chat.command(aliases=['c', 'cc'])
    async def clear_cache(self, ctx: commands.Context):
        """clear chat system cache"""
        for i in self.tasks.values():
            i.cancel()
        for i in self.tasks2.values():
            i[0].cancel()
        self.tasks.clear()
        self.tasks2.clear()
        self.cache.clear()
        self.cache2.clear()
        await ctx.message.add_reaction(emoji="🚮")

    @chat.command(aliases=['h'])
    async def help(self, ctx: commands.Context):
        """show specific command for the chat system"""
        message = "React with specific emoji or reply to bot's embeded message within **120** seconds to:\n\n" \
                  "**Reply** - send the replied message as bot directly into that channel\n" \
                  "💬 - reply to the message\n\n" \
                  "You will have infinite amount of time (unless bot stopped / disconnected) to send a message\n" \
                  "During the wait, you can react to bot's wait message with 🛑 to stop bot's wait for your message"
        await ctx.send(message)

    @chat.command(aliases=['del'])
    async def delete(self, ctx: commands.Context,
                     destination: typing.Union[discord.User, discord.Member, discord.TextChannel, discord.DMChannel],
                     message_id: int):
        """Delete the specified message sent by the bot"""
        target = destination.dm_channel if isinstance(destination, (discord.User, discord.Member)) else destination
        target = await target.fetch_message(message_id)

        if not target:
            return ctx.reply("Can not find the specified message")
        if target.author.id != self.bot.user.id:
            return ctx.reply("That message is not sent by the bot, therefore can't be deleted")

        try:
            await target.delete()
        except (discord.HTTPException, discord.NotFound):
            return ctx.reply("Unknown error has occurred, likely the message is too old to be deleted")
        await ctx.message.add_reaction(emoji="🗑️")

    @chat.command(aliases=['i'])
    async def ignore(self, ctx: commands.Context, target: typing.Union[discord.User, discord.TextChannel, int]):
        """Add a specified ID into the blacklist that prevent message_bot_admins usage"""
        if not isinstance(target, int):
            target = target.id

        if target in self.bl_data:
            self.bl_db.delete_one({"_id": target})
            self.bl_data.remove(target)
            await ctx.message.add_reaction(emoji='➖')
        else:
            self.bl_db.insert_one({"_id": target})
            self.bl_data.append(target)
            await ctx.message.add_reaction(emoji='➕')

    @chat.command(aliases=['il'])
    async def ignore_list(self, ctx: commands.Context, page: int = 1):
        """Show the ignored channel / user ID page"""
        result = ""
        mini = (page - 1) * 30
        maxi = page * 30
        if maxi > len(self.bl_data):
            maxi = len(self.bl_data)
        for i in range(mini, maxi):
            result += f"{self.bl_data[i]}\n"

        max_page = int(maxi / 30) + 1

        await ctx.reply(embed=discord.Embed(
            description="Empty!" if result == "" else result,
            title=f"Ignored List Page {page} / {max_page}",
            color=0x18dcff
        ))

    @chat.command(aliases=['is', 'if'])
    async def ignore_search(self, ctx: commands.Context, target: typing.Union[discord.User, discord.TextChannel, int]):
        """Returns reaction 👍 if the specified target is in the ignore list and 👎 otherwise"""
        if not isinstance(target, int):
            target = target.id

        reply = '👍' if target in self.bl_data else '👎'

        await ctx.message.add_reaction(emoji=reply)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Event listener that processes messages, and decide whether or not to report it to report log channel based on
        chat system data, or process reply messages for the chat system

        Parameters
        ----------
        message: discord.Message
            received new message for processing
        """
        if not message.author.bot:
            check_id = message.author.id if isinstance(message.channel, discord.DMChannel) else message.channel.id

            if check_id in self.data:
                original = embed_message(self.bot, message)
                destinations = self.bot.data.get_report_channels(chat=True)

                for a in original:
                    for i in destinations:
                        temp = await i.send(embed=a)
                        self.tasks[temp.id] = asyncio.get_event_loop().create_task(self.cache_message(temp, message))

            if message.reference:
                try:
                    data = self.cache.pop(message.reference.message_id)
                except KeyError:
                    return

                returned = await send_message(self.bot, data.channel, message)
                await message.reply(content="", embed=returned)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """
        Event listener that process edited messages for the chat system (whether or not to update the embed messages)

        Parameters
        ----------
        before: discord.Message
            the message before edit
        after: discord.Message
            the message after edit
        """
        try:
            destinations = self.cache2[after.id]
        except KeyError:
            return

        if before.content != after.content:
            for i in destinations:
                embed = i.embeds[0]
                embed.description = after.content
                embed.timestamp = datetime.datetime.utcnow()
                await i.edit(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """
        Event listener that updates embed message by chat system if the original message was deleted

        Parameters
        ----------
        message: discord.Message
            deleted message
        """
        try:
            destinations = self.cache2.pop(message.id)
        except KeyError:
            return

        for i in destinations:
            embed = i.embeds[0]
            m = f"~~{message.content}~~" if len(embed.description) < 1996 else f"~~{message.content[:-7]}...~~"
            embed.description = m
            embed.timestamp = datetime.datetime.utcnow()
            await i.edit(embed=embed, content="Now Deleted Message")

            try:
                self.cache.pop(i.id)
            except KeyError:
                pass
            try:
                task = self.tasks.pop(i.id)
                task.cancel()
            except KeyError:
                pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """
        Event listener that checks added reactions by admins through chat system for future states

        Parameters
        ----------
        reaction: discord.Reaction
            the added reaction
        user: discord.User
            user associated with the reaction
        """
        if not self.bot.data.staff_check(user.id):
            return

        if str(reaction.emoji) == '💬':
            m_id = reaction.message.id
            try:
                data = self.cache.pop(m_id)
            except KeyError:
                return

            temp = f"{data.author.mention}'s DMs" \
                if isinstance(data.channel, discord.DMChannel) else data.channel.mention

            string = f"{user.mention} what do you want me to reply to {data.author.mention}'s message in {temp}"

            now = await reaction.message.channel.send(string)
            self.tasks2[now.id] = (asyncio.get_event_loop().create_task(self.wait_for_message(now, data, user)), now)

        if reaction.emoji == '🛑':
            try:
                data = self.tasks2.pop(reaction.message.id)
                data[0].cancel()
                await data[1].edit(content="Operation Cancelled")
            except KeyError:
                pass
