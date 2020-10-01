import discord
import asyncio
from discord.ext import commands
from Components.RaidFilter import RaidFilter


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs. This will update AntiRaid's data from mongoDB.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(AntiRaid(bot))
    print("Load Cog:\tAntiRaid")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("AntiRaid")
    print("Unload Cog:\tAntiRaid")


class AntiRaid(commands.Cog):
    """
    Class inherited from commands.Cog that contains anti-raid commands.

    Attributes
    ----------
    bot : commands.Bot
        commands.Bot reference
    data : dict
        Dictionary containing server's anti-raid system
    db : MongoClient
        MongoDB client reference for "anti-raid" collection
    """

    def __init__(self, bot: commands.Bot):
        """
        Constructor for AntiRaid class.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference for the bot
        """
        self.bot = bot
        self.data = {}
        self.db = bot.mongo["anti-raid"]
        self.update()

    def update(self, guild: int = None):
        """
        Method to update data from MongoDB

        Parameters
        ----------
        guild : int
            the specific server data to update

        Returns
        -------
        RaidFilter
            if guild parameter is not None and data been successfully update, return the RaidFilter reference
        """
        if guild:
            try:
                self.data.pop(guild)
            except KeyError:
                pass
            data = self.db.find_one({"_id": guild})
            if data:
                self.data.update({guild: RaidFilter(self.bot, data)})
                return self.data[guild]
        else:
            self.data.clear()
            data = self.db.find({})
            for i in data:
                self.data.update({i['_id']: RaidFilter(self.bot, i)})

    async def verify(self, ctx: commands.Context):
        """
        Check to see if server have an anti-raid system.

        Parameters
        ----------
        ctx : commands.Context
            pass in context for analysis

        Returns
        -------
        discord.Message
            if there is no anti-raid system, return the alert message sent
        RaidFilter
            if server contains anti-raid, return RaidFilter class associated with that server
        """
        try:
            return self.data[ctx.guild.id]
        except KeyError:
            return await ctx.send(f"This server have not setup an anti-raid yet. Do "
                                  f"`{ctx.prefix}ar create <raider role>` to set it up.")

    def database_update(self, data: RaidFilter):
        """
        Method to update the mongoDB data from RaidFilter class data.

        Parameters
        ----------
        data : RaidFilter
            RaidFilter class date to update MongoDB
        """
        self.db.update_one({"_id": data.guild_id},
                           {"$set": {"power": data.switch, "interval": data.interval, "amount": data.count,
                                     "role_id": data.role_id, "timeout": data.timeout}})

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Cog event that calls this method when a member joins the server. Add the new member to either holding cell
        or raid cell if applicable.

        Parameters
        ----------
        member : discord.Member
            The newly joined member
        """
        try:
            data = self.data[member.guild.id]
        except KeyError:
            return
        if data.switch:
            await data.new_member(member)

    @commands.guild_only()
    @commands.group(aliases=['ar'])
    @commands.has_permissions(ban_members=True, kick_members=True)
    async def anti_raid(self, ctx: commands.Context):
        """Anti-raid group commands. Calling this without additional parameter will return command help."""
        if not ctx.invoked_subcommand:
            pre = ctx.prefix
            embed = discord.Embed(
                title="`Anti Raid` Commands",
                colour=0xf368e0
            )
            embed.add_field(inline=False, name=f"{pre}ar create <raider role mention or ID>",
                            value="Create anti raid system with given raider role")
            embed.add_field(inline=False, name=f"{pre}ar clear (True or False)",
                            value="Turn off the anti raid alarm if it's on, and pass in whether or not to free all "
                                  "marked raiders. Default is no.")
            embed.add_field(inline=False, name=f"{pre}ar raid (True or False)",
                            value="Turn on the anti raid mode and put recent members into the raid cell indefinitely. "
                                  "Additional parameter for if the raid mode is indefinite, default is yes.")
            embed.add_field(inline=False, name=f"{pre}ar kick (True or False)",
                            value="Kick all members inside the anti raid cell and pass in whether or not "
                                  "to switch off the anti raid alarm. Default is no.")
            embed.add_field(inline=False, name=f"{pre}ar ban (True or False)",
                            value="Ban all members inside the anti raid cell and pass in whether or not to"
                                  " switch off the anti raid alarm. Default is yes.")
            embed.add_field(inline=False, name=f"{pre}ar status (Page#)", value="Show anti raid cell status.")
            embed.add_field(inline=False, name=f"{pre}ar + <member mention or ID>",
                            value="Add the target into the anti raid cell.")
            embed.add_field(inline=False, name=f"{pre}ar - <user mention or ID>",
                            value="Remove the target from the anti raid cell if they are in it.")
            embed.add_field(inline=False, name=f"{pre}ar s", value="Bring up anti raid setting menu")
            await ctx.send(embed=embed)

    @anti_raid.command()
    async def clear(self, ctx: commands.Context, release: bool = False):
        """Turn off raid mode and pass in additional argument to whether or not to release all users from raid cell."""
        data = await self.verify(ctx)
        if isinstance(data, RaidFilter):
            data.raid = False
            if not release:
                await ctx.message.add_reaction(emoji='✔')
            else:
                ret = await data.release_all()
                for i in ret:
                    await ctx.send(embed=discord.Embed(title="Free marked raiders",
                                                       colour=0x4cd137, description=i))

    @anti_raid.command()
    async def raid(self, ctx: commands.Context, indefinite: bool = True):
        """Turn on raid mode and send all user in holding cell to raid cell.
        Additional parameter whether or not the raid mode is indefinite."""
        data = await self.verify(ctx)
        if not isinstance(data, discord.Message):
            await data.triggered(indefinite)
            await ctx.message.add_reaction(emoji="🏃")

    @anti_raid.command()
    async def ban(self, ctx: commands.Context, stop: bool = True):
        """Ban all users with server's raider role and turn off raid mode as default (can be specified)."""
        data = await self.verify(ctx)
        if isinstance(data, RaidFilter):
            result = list(await data.ban_all(ctx, stop))
            await ctx.message.add_reaction(emoji='✅')
            for i in range(len(result)):
                await ctx.send(
                    embed=discord.Embed(title=f"All Banned Raiders {i + 1}", description=result[i], colour=0xff4757)
                )

    @anti_raid.command()
    async def kick(self, ctx: commands.Context, stop: bool = True):
        """Kick all users with server's raider role and turn off raid mode as default (can be specified)."""
        data = await self.verify(ctx)
        if isinstance(data, RaidFilter):
            result = list(await data.kick_all(stop))
            await ctx.message.add_reaction(emoji='✅')
            for i in range(len(result)):
                await ctx.send(
                    embed=discord.Embed(title=f"All Kicked Raiders {i + 1}", description=result[i], colour=0xff4757)
                )

    @anti_raid.command()
    async def create(self, ctx: commands.Context, role: discord.Role):
        """Create an anti-raid system for the server with the specified raider role."""
        data = self.db.find_one({"_id": ctx.guild.id})
        if data:
            return await ctx.send("This server already have an anti-raid system, no need to create another one.")
        self.db.insert_one({"_id": ctx.guild.id, "interval": 5, "amount": 3, "power": True, "role_id": role.id,
                            "timeout": 60})
        self.update(ctx.guild.id)
        await ctx.message.add_reaction(emoji='👍')

    @anti_raid.command()
    async def status(self, ctx: commands.Context, page: int = 1):
        """Return people in the server who are marked as raiders."""
        data = await self.verify(ctx)
        if isinstance(data, RaidFilter):
            if not data.switch:
                return await ctx.send("Anti Raid system is not online")
            embed = discord.Embed(
                colour=0xe056fd,
                title="AntiRaid Status " + ("⚠ RAID!" if data.raid else "🧘 Clear"),
                timestamp=ctx.message.created_at
            )
            raid = list(data.raiders_to_string())
            hold = list(data.holding_to_string())

            if len(raid) >= page:
                temp = raid[page - 1]
                if temp != '':
                    embed.add_field(name=f"Raid Cell {page}", value=temp)

            if len(hold) >= page:
                temp = hold[page - 1]
                if temp != '':
                    embed.add_field(name=f"Watch List {page}", value=temp)

            await ctx.send(embed=embed)

    @anti_raid.command(aliases=['+'])
    async def mark(self, ctx: commands.Context, *target: discord.Member):
        """Mark target users as raider."""
        data = await self.verify(ctx)
        if isinstance(data, RaidFilter):
            for i in target:
                try:
                    await data.add(i)
                except ValueError:
                    await ctx.send(f"{i.mention} is already a marked raider")
            await ctx.message.add_reaction(emoji='👍')

    @anti_raid.command(aliases=['-'])
    async def unmark(self, ctx: commands.Context, *target: discord.Member):
        """Remove users from raid cell."""
        data = await self.verify(ctx)
        if isinstance(data, RaidFilter):
            for i in target:
                try:
                    await data.remove(i)
                except ValueError:
                    await ctx.send(f"Can not find {i.mention} within raider cell")
            await ctx.message.add_reaction(emoji='👍')

    @anti_raid.command(aliases=['s'])
    async def setting(self, ctx: commands.Context):
        """Brings up anti-raid setting menu."""
        emotes = ['💡', '👪', '⏱', '📛', '😴', '⏸']

        def check(reaction1, user1):
            return reaction1.emoji in emotes and user1.id == ctx.author.id

        data = await self.verify(ctx)
        if isinstance(data, RaidFilter):
            de_role = ctx.guild.get_role(data.role_id)
            embed = discord.Embed(
                title="Anti-Raid Setting Menu " + ("[Active]" if data.switch else "[Inactive]"),
                colour=0x2ecc71 if data.switch else 0xc0392b,
                timestamp=ctx.message.created_at,
                description=f"💡 - Toggle Anti-Raid \n👪 - Amount of People Required to Trigger [{data.count}]\n"
                            f"⏱ - Timer [{data.interval} seconds]\n"
                            f"😴 - Raid Timeout: {data.timeout} seconds \n"
                            f"📛 - Raider Role: " + (f"{de_role.mention}" if de_role else "**Error!!**") + "\n"
                            f"⏸ - Setting Menu Pause"
            ).set_footer(text="React to Modify", icon_url=self.bot.user.avatar_url_as(size=128))
            msg = await ctx.send(embed=embed)
            for i in emotes:
                await msg.add_reaction(emoji=i)
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)
            except asyncio.TimeoutError:
                await msg.edit(embed=embed.set_footer(text="Menu Timed Out",
                                                      icon_url=self.bot.user.avatar_url_as(size=64)))
                return await msg.clear_reactions()
            await msg.clear_reactions()

            def check_m(message):
                return message.author.id == ctx.author.id

            if reaction.emoji == '⏸':
                await msg.edit(
                    embed=embed.set_footer(text="Menu Paused", icon_url=self.bot.user.avatar_url_as(size=64)))
            elif reaction.emoji == "💡":
                result = data.toggle()
                await msg.edit(embed=None, content="Anti-Raid now enabled" if result else "Anti-Raid now disabled")
            elif reaction.emoji == '📛':
                await msg.edit(embed=None, content="Enter the role ID of the new raider role.")
                try:
                    m = await self.bot.wait_for('message', timeout=20, check=check_m)
                except asyncio.TimeoutError:
                    return await msg.edit(content="Anti-Raid Menu Timed Out.")
                try:
                    rol = ctx.guild.get_role(int(m.content))
                except ValueError:
                    return await msg.edit(content="Input not a number, action cancelled.")
                if not rol:
                    return await msg.edit(content="Role not found, action cancelled")
                await data.update_role(rol)
                await msg.edit(content=f"Changed raid role to {data.role.mention}")
            else:
                store = {
                    '👪': "Enter the amount(integer) of user join needed to trigger",
                    '⏱': "Enter the amount(integer) in seconds of the interval",
                    '😴': "Enter the amount(integer) in seconds for Anti-Raid to time itself out"
                }
                try:
                    await msg.edit(embed=None, content=store[reaction.emoji])
                    m = await self.bot.wait_for('message', timeout=10, check=check_m)
                    try:
                        m = int(m.content)
                    except ValueError:
                        return await msg.edit(content="Value entered is not an integer. Action cancelled")
                    if m < 1:
                        return await msg.edit(content="Value must be 1 or bigger")
                    if reaction.emoji == '👪':
                        data.count = m
                        await msg.edit(content=f"member join flow holder is now set to `{m}` people")
                    elif reaction.emoji == '😴':
                        data.timeout = m
                        await msg.edit(content=f"Anti-raid automatic timeout is now set to __{m}__ seconds")
                    else:
                        data.interval = m
                        await msg.edit(content=f"member join timer is now set **{m}** seconds")
                except asyncio.TimeoutError:
                    return await msg.edit(content="Anti-Raid Menu Timed Out.")
            self.database_update(data)
