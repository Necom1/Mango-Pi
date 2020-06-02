import typing
import discord
import traceback
from discord.ext import commands


def is_admin(ctx: commands.Context):
    """
    Function that returns the Admin class check result for commands.Check

    Parameters
    ----------
    ctx : commands.Context
        pass in context to check

    Returns
    -------
    bool
        Whether or not the author is an admin
    """
    return ctx.bot.admins.check(ctx)


class Management(commands.Cog):
    """
    Class inherited from commands.Cog that contains Cog management commands for bot admins and owner.

    Attributes
    ----------
    bot : commands.Bot
        commands.Bot reference
    illegal : list
        list containing Cogs that can not be unload or reload by bot administrators
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor for Management class.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference for the Cog
        """
        self.bot = bot
        self.illegal = ['Management']

    @commands.command(aliases=['cs', 'ms'])
    @commands.check(is_admin)
    async def modules_status(self, ctx: commands.Context):
        """Bot administrators command to check bot's cog status."""
        loaded = [f"+ **{i}**" if i not in self.illegal else f"+ __**{i}**__" for i in self.bot.loaded_cogs.keys()]
        unloaded = [f"- ~~{i}~~" for i in self.bot.unloaded_cogs.keys()]
        embed = discord.Embed(
            colour=0xFFB300,
            title="System Cog Status",
            timestamp=ctx.message.created_at
        ).set_footer(icon_url=self.bot.user.avatar_url, text="")
        embed.add_field(name=f"Active Cogs [{len(self.bot.loaded_cogs)}]",
                        value="\n".join(loaded) if len(loaded) > 0 else "None", inline=False)
        embed.add_field(name=f"Inactive Cogs [{len(self.bot.unloaded_cogs)}]",
                        value="\n".join(unloaded) if len(unloaded) > 0 else "None", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_admin)
    async def reload(self, ctx: commands.Context, cog: str):
        """Bot administrators only command that reloads a specified Cog."""
        if cog in self.illegal:
            return await ctx.send("Can not reload a vital Cog.")

        try:
            target = self.bot.loaded_cogs[cog]
        except KeyError:
            return await ctx.send(f"No loaded Cog with the name: {cog}")

        try:
            self.bot.unload_extension(target)
            self.bot.load_extension(target)
            embed = discord.Embed(
                title="COG Reloaded ♻", colour=0x1dd1a1, timestamp=ctx.message.created_at,
                description=f"[**{cog}**] module got reloaded!")
            await ctx.send(embed=embed)
        except Exception as ex:
            print(f"**{cog}** failed to reload:")
            await ctx.send(f"```py\n{traceback.format_exc()}\n```")
            raise ex

    @commands.command()
    @commands.check(is_admin)
    async def load(self, ctx: commands.Context, cog: str):
        """ Bot administrators only command that reloads a specified Cog."""
        try:
            target = self.bot.unloaded_cogs[cog]
        except KeyError:
            return await ctx.send(f"No unloaded Cog with the name: {cog}")

        try:
            self.bot.load_extension(target)
            embed = discord.Embed(
                title="COG Loaded ↪", colour=0x12CBC4, timestamp=ctx.message.created_at,
                description=f"[**{cog}**] module has been loaded!")
            await ctx.send(embed=embed)
            self.bot.loaded_cogs.update({cog: self.bot.unloaded_cogs.pop(cog)})
        except Exception as ex:
            print(f"Failed to load {cog}:")
            await ctx.send(f"```py\n{traceback.format_exc()}\n```")
            raise ex

    @commands.command()
    @commands.check(is_admin)
    async def unload(self, ctx: commands.Context, cog: str):
        """Bot administrators only command that unload an active Cog. """
        if cog in self.illegal:
            return await ctx.send("Can not unload a vital Cog.")

        try:
            target = self.bot.loaded_cogs[cog]
        except KeyError:
            return await ctx.send(f"No loaded Cog with the name: {cog}")

        try:
            self.bot.unload_extension(target)
            embed = discord.Embed(
                title="COG Unloaded ⬅", colour=0xEA2027, timestamp=ctx.message.created_at,
                description=f"[**{cog}**] module got unloaded!")
            await ctx.send(embed=embed)
            self.bot.unloaded_cogs.update({cog: self.bot.loaded_cogs.pop(cog)})
        except Exception as ex:
            print(f"**{cog}** failed to unload:")
            await ctx.send(f"```py\n{traceback.format_exc()}\n```")
            raise ex

    @commands.command(aliases=['+staff'])
    @commands.is_owner()
    async def add_staff(self, ctx: commands.Context, target: typing.Union[discord.Member, discord.User, int]):
        """Bot owner only command that add a user to bot's administrator list."""
        if isinstance(target, int):
            try:
                target = await self.bot.fetch_user(target)
            except discord.NotFound:
                return await ctx.send("Can not find that user.")
        try:
            ret = self.bot.admins.add(target.id)
        except RuntimeError:
            return await ctx.send("Current busy, please try again later.")
        if ret:
            await ctx.send(ret)
        else:
            await ctx.message.add_reaction(emoji='👍')
            await ctx.send(f"Added **{target}** to administrator list.")

    @commands.command(aliases=['-staff'])
    @commands.is_owner()
    async def remove_staff(self, ctx: commands.Context, target: typing.Union[discord.Member, discord.User, int]):
        """Bot owner only command that removes a user from bot's administrator list."""
        if not isinstance(target, int):
            target = target.id
        try:
            ret = self.bot.admins.remove(target)
        except RuntimeError:
            return await ctx.send("Current busy, please try again later.")
        if ret:
            await ctx.send(ret)
        else:
            await ctx.message.add_reaction(emoji='👍')
            await ctx.send(f"Removed user with ID of **{target}** from administrator list.")


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(Management(bot))
    print("Load Cog:\tManagement")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("Management")
    print("Unload Cog:\tManagement")
