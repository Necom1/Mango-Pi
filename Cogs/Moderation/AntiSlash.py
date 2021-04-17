import discord
import asyncio
from discord.ext import commands
from Components.MangoPi import highest_role_position


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(AntiSlash(bot))
    print("Load Cog:\tAntiSlash")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("AntiSlash")
    print("Unload Cog:\tAntiSlash")


class AntiSlash(commands.Cog):
    """
    Class inherited from commands.Cog that contains commands to remove or list roles with slash perms

    Attributes
    ----------
    bot: commands.Bot
        bot reference
    api_limit: list
        list that contains server ID that disallows use of removing perms from roles for 1 hr
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor of AntiSlash class

        Parameters
        ----------
        bot: commands.Bot
            pass in bot reference
        """
        self.bot = bot
        self.api_limit = []

    @staticmethod
    def slash_perm_check(arr: list, reverse: bool = False):
        """
        Method that checks the passed in array and filters it

        Parameters
        ----------
        arr: list
            array of discord roles to filter
        reverse: bool
            return roles without the permission to use slash perm instead, default false

        Returns
        -------
        tuple
            the filtered discord roles
        """
        ret = []

        for i in arr:
            if not reverse:
                if i.permissions.use_slash_commands:
                    ret.append(i)
            if reverse:
                if not i.permissions.use_slash_commands:
                    ret.append(i)

        return tuple(ret)

    @commands.guild_only()
    @commands.command(aliases=["check/"])
    @commands.has_permissions(manage_roles=True)
    async def check_slash(self, ctx: commands.Context):
        """Check all server roles to see if there is roles that have the permission to use slash commands"""
        embed = discord.Embed(
            colour=0xfbc531,
            title="Roles with Slash command permission",
            description="None! Nice!",
            timestamp=ctx.message.created_at
        )
        to_send = [embed.copy()]
        roles = self.slash_perm_check(ctx.guild.roles)
        if len(roles) > 0:
            page = 0
            string = ""
            for i in range(len(roles)):
                string += f"{roles[i].mention}\n"
                if (i % 25 == 0 and i != 0) or len(roles) - 1 == i:
                    to_send[page].description = string
                    string = ""
                    page += 1
                    to_send[page-1].title = f"Roles with Slash command permission {page}"
                    if len(roles) - 1 != i:
                        to_send.append(embed.copy())

        for i in to_send:
            await ctx.reply(embed=i)

    @commands.guild_only()
    @commands.command(aliases=["no/"])
    @commands.has_permissions(manage_roles=True)
    async def no_slash(self, ctx: commands.Context):
        """Attempt to remove permission to use slash commands from all roles of the server,
        1 hour cooldown after use."""
        if ctx.guild.id in self.api_limit:
            return ctx.reply("API call cooldown, please try again later")
        else:
            self.api_limit.append(ctx.guild.id)

        roles = self.slash_perm_check(ctx.guild.roles)
        hoist = highest_role_position(ctx.me.roles)

        msg = await ctx.reply(f"0 / {len(roles)} roles modified")

        success = []
        no_perm = []
        failed = []
        for i in range(len(roles)):
            perm = roles[i].permissions
            perm.use_slash_commands = False
            if roles[i].position < hoist:
                try:
                    await roles[i].edit(permissions=perm,
                                        reason=f"Remove use slash command perm by {ctx.message.author}")
                    success.append(roles[i])
                except discord.HTTPException:
                    failed.append(roles[i])
            else:
                no_perm.append(roles[i])
            if i != 0 and i % 10 == 0:
                await msg.edit(content=f"{i} / {len(roles)} roles modified...")

        await msg.delete()

        sends = []
        embed_format = discord.Embed(
            colour=0x1abc9c,
            title="Successfully modified roles",
            description="None...",
            timestamp=ctx.message.created_at
        )

        def appending_result(arr: list):
            if len(arr) > 0:
                page = 0
                string = ""
                for a in range(len(arr)):
                    string += f"{arr[a].mention}\n"
                    if (a % 25 == 0 and a != 0) or len(arr) - 1 == a:
                        sends.append(embed_format.copy())
                        sends[len(sends) - 1].description = string
                        string = ""
                        page += 1
                        sends[len(sends) - 1].title = f"{sends[len(sends) - 1].title} {page}"

        appending_result(success)
        embed_format.title = "Not enough permission to modify the following roles"
        embed_format.colour = 0xf1c40f
        appending_result(no_perm)
        embed_format.title = "Failed to modify the following roles"
        embed_format.colour = 0xe74c3c
        appending_result(failed)
        for i in sends:
            await ctx.reply(embed=i)

        await asyncio.sleep(3600)
        self.api_limit.remove(ctx.guild.id)
