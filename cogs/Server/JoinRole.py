import discord
import typing
from pymongo import MongoClient
from discord.ext import commands


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(JoinRole(bot))
    print("Load Cog:\tJoinRole")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("JoinRole")
    print("Unload Cog:\tJoinRole")


class AutoRole:
    """
    Class representing a server's join role system.

    Attributes
    ----------
    guild_id: int
        guild ID for that server
    roles_id: list
        list of IDs of the roles to assign to new incoming members
    power: bool
        whether or not join role system is enabled for the server
    roles: list
        list of discord.Role to assign to new incoming members
    """
    def __init__(self, bot: commands.Bot, package: dict):
        """
        Constructor for AutoRole class.

        Parameters
        ----------
        bot: commands.Bot
            pass in bot to help locate roles
        package
            pass in mongo data to initialize the class
        """
        self.guild_id = package["_id"]
        self.roles_id = package["role_array"]
        self.power = package["switch"]
        self.roles = []
        if self.change(bot):
            self.update(bot.mongo["join_auto"])

    def update(self, client: MongoClient):
        """
        Method that accepts a passed in MongoClient and update mongo database with the information within the class

        Parameters
        ----------
        client: MongoClient
            pass in mongo client linked to "join_auto" to update existing JoinRole data
        """
        client.update({"_id": self.guild_id}, {"$set": {"role_array": self.roles_id, "switch": self.power}})

    def change(self, bot: commands.Bot):
        """
        Method used to update roles list from role_ids.

        Parameters
        ----------
        bot: commands.Bot
            pass in bot to find the roles within role_ids

        Returns
        -------
        bool
            whether or not system have failed to retrieve one or more roles
        """
        ret = False
        self.roles.clear()
        server = bot.get_guild(self.guild_id)
        for i in self.roles_id:
            temp = server.get_role(i)
            if temp:
                self.roles.append(temp)
            else:
                ret = True
                self.roles_id.remove(i)
        return ret

    def to_str(self):
        """
        Method that converts roles within the system into mention sting

        Returns
        -------
        str
            mentioned roles
        """
        ret = ""
        for i in self.roles:
            ret += f"{i.mention}\n"
        return ret

    async def new(self, member: discord.Member):
        """
        Async method that adds the role to the passed in member

        Parameters
        ----------
        member: discord.Member
            the member to add all the roles within the system to
        """
        if self.power and len(self.roles) > 0:
            await member.add_roles(*self.roles, reason="Role on join system")


class JoinRole(commands.Cog):
    """
    Class inherited from commands.Cog that contains JoinRole commands.

    Attributes
    ----------
    bot: commands.Bot
        bot reference
    db: MongoClient
        the MongoClient reference to the join_auto collection
    data: dict
        the dictionary that holds AutoRole class for the specific server
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor for the JoinRole class

        Parameters
        ----------
        bot: commands.Bot
            pass in bot reference
        """
        self.bot = bot
        self.db = bot.mongo["join_auto"]
        self.data = {}
        self.update()

    def search(self, guild: int):
        """
        Method for finding the AutoRole class within the data dictionary

        Parameters
        ----------
        guild: int
            pass guild ID to find the AutoRole within the data dictionary

        Returns
        -------
        AutoRole
            reference for the AutoRole class for that passed in server, None if nothing is found
        """
        try:
            return self.data[guild]
        except KeyError:
            return

    def update(self, guild: int = None):
        """
        Method to update data dictionary from mongo database. Either update the entire data dictionary or just that
        server.

        Parameters
        ----------
        guild: int
            server ID to update if any
        """
        if guild:
            try:
                self.data.pop(guild)
            except KeyError:
                pass
            data = self.db.find({"_id": guild})
        else:
            self.data.clear()
            data = self.db.find()
        if data:
            for i in data:
                self.data.update({i['_id']: AutoRole(self.bot, i)})

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Event listener that be called when new member joins the server. This async method will try to locate the
        AutoRole class within the data dictionary to add the appropriate roles to the new member

        Parameters
        ----------
        member: discord.Member
            the newly joined member
        """
        if not member.bot:
            data = self.search(member.guild.id)
            if data:
                await data.new(member)

    @commands.group(aliases=['jr'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def join_role(self, ctx: commands.Context):
        """Group of join_role commands, call it without sub-command to bring up list join roles for the server"""
        if not ctx.invoked_subcommand:
            data = self.search(ctx.guild.id)
            if not isinstance(data, AutoRole):
                await ctx.send("Join role system not set")
            else:
                temp = data.to_str()
                status = "Join role list " + ("[On]" if data.power else "[Off]")
                await ctx.send(embed=discord.Embed(
                    title=status,
                    colour=0x2ecc71 if data.power else 0xe74c3c,
                    description=temp
                ))

    @join_role.command()
    async def purge(self, ctx: commands.Context):
        """Removes all the roles within the Join Role system"""
        data = self.search(ctx.guild.id)
        if not data:
            await ctx.send("Nothing to purge")
        else:
            self.db.delete_one({"_id": ctx.guild.id})
            self.update(ctx.guild.id)
            await ctx.send("Join role system purged.")

    @join_role.command(aliases=['t'])
    async def toggle(self, ctx: commands.Context):
        """Toggles on and off for the Join Role system"""
        data = self.search(ctx.guild.id)

        if not data:
            await ctx.send("No join role system for this server")
        else:
            data.power = not data.power
            status = "On" if data.power else "Off"
            self.db.update_one({"_id": ctx.guild.id}, {"$set": {"switch": data.power}})
            await ctx.send(f"Join role system is now {status}")

    @join_role.command(aliases=['+'])
    async def add(self, ctx: commands.Context, *roles: discord.Role):
        """Add roles by mention or ID into the Join Role system"""
        data = self.search(ctx.guild.id)
        if not data:
            ids = []
            for i in roles:
                ids.append(i.id)
            self.db.insert_one({"_id": ctx.guild.id, "role_array": ids, "switch": True})
            temp = ""
            for i in roles:
                temp += f"{i.mention}\n"
            self.update(ctx.guild.id)
            await ctx.send(embed=discord.Embed(
                title="Added these role(s) into the join role system",
                colour=0x74b9ff,
                description=temp
            ))
        else:
            adds = ""
            fails = ""
            for i in roles:
                if i not in data.roles_id:
                    adds += f"{i.mention}\n"
                    data.roles_id.append(i.id)
                else:
                    fails += f"{i.mention}\n"
            if data.change(self.bot):
                data.update(self.db)
            embed = discord.Embed(title="Updated role(s) in the join role system", colour=0x55efc4)
            embed.add_field(name="Added Role(s)", value="None" if adds == "" else adds, inline=False)
            embed.add_field(name="Failed to add", value="None" if fails == "" else fails, inline=False)
            await ctx.send(embed=embed)

    @join_role.command(aliases=['-'])
    async def remove(self, ctx: commands.Context, *roles: typing.Union[discord.Role, int]):
        """Removes roles form the join role system by role mention or ID"""
        data = self.search(ctx.guild.id)

        if not data:
            return await ctx.send("Join role system is not setup")

        removes = ""
        fails = ""
        for i in roles:
            num = i.id if isinstance(i, discord.Role) else i
            try:
                data.roles_id.remove(num)
            except ValueError:
                fails += f"<@&{num}>\n"
            else:
                removes += f"<@&{num}>\n"

        if data.change(self.bot):
            self.update(self.db)

        embed = discord.Embed(
            title="Updated roles in the join role system",
            colour=0xe74c3c
        )
        embed.add_field(name="Removed roles", value="None" if removes == "" else removes, inline=False)
        embed.add_field(name="Failed to remove", value="None" if fails == "" else fails, inline=False)
        await ctx.send(embed=embed)
