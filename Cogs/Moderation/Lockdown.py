import discord
import asyncio
from discord.ext import commands
from Components.MangoPi import MangoPi


def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs. This will update Lockdown's data from mongoDB.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog
    """
    bot.add_cog(Lockdown(bot))
    print("Load Cog:\tLockdown")


def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog
    """
    bot.remove_cog("Lockdown")
    print("Unload Cog:\tLockdown")


class Lockdown(commands.Cog):
    """
    Class Lockdown inherited from commands.Cog and contains Lockdown commands

    Attributes
    ----------
    self.bot: MangoPi
        MangoPi reference for functionality
    db: MongoClient
        lockdown MongoDB reference
    data: dict
        dictionary holding roles aline with the data of MongoDB
    cooldown: dict

    """

    def __init__(self, bot: MangoPi):
        """
        Constructor for Lockdown class

        Parameters
        ----------
        bot: MangoPi
            pass in MangoPi reference
        """
        self.bot = bot
        self.db = bot.mongo["lockdown"]
        self.data = {}
        self.cooldown = []
        self.update()

    def update(self, specific: int = None):
        """
        Method that attempts to update data with roles based on input from MongoDB

        Parameters
        ----------
        specific: int
            ID of a specific server to update
        """
        fetch = self.db.find_one({'_id': specific}) if specific else self.db.find({})
        for i in fetch:
            server = self.bot.get_guild(i['_id'])
            if server:
                role = server.get_role(i['role'])
                if role:
                    self.data[i['_id']] = role

    def search(self, server: int):
        """
        Function that searches data and return result base on server ID input

        Parameters
        ----------
        server: int
            server ID associated with the target

        Returns
        -------
        discord.Role
            the role to target for locking down channels
        """
        try:
            return self.data[server]
        except KeyError:
            return None

    @commands.group(aliases=['lm'])
    @commands.has_permissions(manage_channels=True)
    async def lockmenu(self, ctx: commands.Context):
        """Lock menu that shows the current target roles for lock and unlock commands"""
        if not ctx.invoked_subcommand:
            data = self.search(ctx.guild.id)
            if not data:
                return await ctx.reply("No roles setup to target, will target the `everyone` role instead.")

            embed = discord.Embed(
                colour=data.colour,
                description=data.mention,
                title="Targeted Role for Lockdown"
            )
            await ctx.reply(embed=embed)

    @lockmenu.command(aliases=['s'])
    async def set(self, ctx: commands.Context, role: discord.Role = None):
        """Set the default target role for the lock or unlock command"""
        data = self.search(ctx.guild.id)
        if not role and not data:
            return await ctx.message.add_reaction(emoji='🙁')

        if role:
            self.data[ctx.guild.id] = role
            if not data:
                self.db.insert_one({'_id': ctx.guild.id, 'role': role.id})
            else:
                self.db.update_one({'_id': ctx.guild.id},
                                   {'$set': {'role': role.id}})
        else:
            self.db.delete_one({'_id': ctx.guild.id})
            self.data.pop(ctx.guild.id)
        await ctx.message.add_reaction(emoji='👍')

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, text: commands.Greedy[discord.TextChannel],
                   vc: commands.Greedy[discord.VoiceChannel], *roles: discord.Role):
        """Locks a channel's send message perm for set or specified roles"""
        if await self.process(ctx, text, vc, list(roles), False):
            self.cooldown.append(ctx.guild.id)
            await ctx.message.add_reaction(emoji='🔒')
            await asyncio.sleep(10)
            self.cooldown.remove(ctx.guild.id)

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context, text: commands.Greedy[discord.TextChannel],
                     vc: commands.Greedy[discord.VoiceChannel], *roles: discord.Role):
        """Unlocks a channel's send message perm for set or specified roles"""
        if await self.process(ctx, text, vc, list(roles)):
            self.cooldown.append(ctx.guild.id)
            await ctx.message.add_reaction(emoji='🔓')
            await asyncio.sleep(10)
            self.cooldown.remove(ctx.guild.id)

    async def process(self, ctx: commands.Context, text: list, vc: list, roles: list, special: bool = None):
        """
        Async method that attempts to lock or unlock channels based on input

        Parameters
        ----------
        ctx: commands.Context
            pass in context for reply
        text: list
            list of text channels to lock or unlock
        vc: list
            list of voice channels to lock or unlock
        roles: list
            list of target roles for the channel lock or unlock
        special: bool
            the state of the permissions for the channels. None or True to unlock, False to lock.

        Returns
        -------
        bool
            whether or not the operation is a success
        """
        if ctx.guild.id in self.cooldown:
            await ctx.reply("Command in cooldown, please wait before using the command again.", delete_after=10)
            return False
        if (len(vc) + len(text)) * len(roles) > 5:
            await ctx.reply("Too much API calls, place reduce amount of targets and roles.", delete_after=10)
            return False

        if len(text) + len(vc) < 1:
            text.append(ctx.channel)

        data = self.search(ctx.guild.id)
        if len(roles) < 1:
            roles.append(data if data else ctx.guild.default_role)

        merged = text + vc

        for i in merged:
            for r in roles:
                maps = i.overwrites
                overwrite = maps[r]
                if isinstance(i, discord.TextChannel):
                    overwrite.send_messages = special
                else:
                    overwrite.speak = special
                await i.set_permissions(r, overwrite=overwrite)

        return True
