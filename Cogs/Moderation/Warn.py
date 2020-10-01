import typing
import discord
import datetime
from discord.ext import commands


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(Warn(bot))
    print("Load Cog:\tWarn")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("Warn")
    print("Unload Cog:\tWarn")


class Warn(commands.Cog):
    """
    Class inherited from commands.Cog that contains warn commands.

    Attributes
    ----------
    bot: commands.Bot
        bot reference
    db: MongoClient
        mongo reference to the warns collection
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor for Warn class

        Parameters
        ----------
        bot: commands.Bot
            pass in bot reference
        """
        self.bot = bot
        self.db = bot.mongo["warns"]

    def add_warn(self, time: datetime.datetime, guild: int, user: int, warner: int, kind: int, reason: str,
                 additional: str = None):
        """
        Method that adds a warning to the user warn list within the mongo database.

        Parameters
        ----------
        time: datetime.datetime
            time of the warn
        guild: int
            ID of the server where the warn occurred
        user: int
            ID of the user being warned
        warner: int
            ID of the warner if the warn is manual
        kind: int
            indicate of what kind of warn it is.
        reason: str
            the warn reason
        additional: str
            additional information if the kind of warn is mute
        """
        ret = 1
        data = self.db.find_one({"guild_id": guild, "user_id": user})
        time = time.strftime("%#d %B %Y, %I:%M %p UTC")
        if data:
            self.db.update_one({"guild_id": guild, "user_id": user},
                               {"$push": {"warn_id": data["max"], "kind": kind, "warner": warner, "reason": reason,
                                          "time": time, "addition": additional}})
            self.db.update_one({"guild_id": guild, "user_id": user}, {"$inc": {"max": 1}})
            ret = len(data["warn_id"]) + 1
        else:
            self.db.insert_one({"guild_id": guild, "user_id": user, "warn_id": [1], "kind": [kind], "warner": [warner],
                                "reason": [reason], "time": [time], "addition": [additional], "max": 2})

        return ret

    @commands.command(aliases=['w'])
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def warn(self, ctx: commands.Context, target: discord.Member, *, reason: str):
        """Warns a member and adds that to their warn list"""
        if target.bot:
            return await ctx.send("Bots don't list to warnings...")
        if len(reason) <= 0:
            return await ctx.send("Please specify a reason.")
        if ctx.author.id == target.id:
            return await ctx.send("Wait, what?")
        if len(reason) > 400:
            return await ctx.send("That is a very long warning reason... Try keep in under 400 letters...")

        data = self.add_warn(ctx.message.created_at, ctx.guild.id, target.id, ctx.author.id, 0, reason)

        try:
            await target.send("⚠ You received a warning ⚠", embed=discord.Embed(
                timestamp=ctx.message.created_at,
                description=reason,
                colour=0xd63031
            ).set_footer(icon_url=target.avatar_url_as(size=64), text=f"{data} offenses")
                              .set_author(icon_url=ctx.guild.icon_url_as(size=64), name=f"{ctx.guild.name}"))
            await ctx.message.add_reaction(emoji='👍')
        except discord.HTTPException:
            await ctx.send("Warning stored in system, however, can not warn the target via DM.")

    @commands.guild_only()
    @commands.group(aliases=['wm'])
    @commands.has_permissions(ban_members=True)
    async def warn_menu(self, ctx: commands.Context):
        """Group command of warn_menu, if called with no additional specification, list of sub-command will be shown"""
        if not ctx.invoked_subcommand:
            embed = discord.Embed(title="`Warn Menu` Commands", colour=0x9b59b6)
            embed.add_field(inline=False, name=f"{ctx.prefix}wm <mode> <User ID/Mention> (warning ID )",
                            value="Mode 'show' will list amount of warning the user have\nMode 'purge' will delete all"
                                  " the warnings the user have\nMode 'remove' will remove the specified warnings "
                                  "the user have by warn ID")
            await ctx.send(embed=embed)

    @warn_menu.command()
    async def purge(self, ctx, target: typing.Union[discord.Member, discord.User, int]):
        """Remove all the warns this user may have"""
        if isinstance(target, int):
            target = target
        else:
            target = target.id

        self.db.delete_one({"guild_id": ctx.guild.id, "user_id": target})
        await ctx.send(f"Purged warn data of user with ID:`{target}`")

    @warn_menu.command(aliases=['-'])
    async def remove(self, ctx: commands.Context, target: typing.Union[discord.Member, discord.User, int], warn: int):
        """Remove the specified warn by warn ID that the user have"""
        if isinstance(target, int):
            target = target
        else:
            target = target.id

        data = self.db.find_one({"guild_id": ctx.guild.id, "user_id": target})
        if data is None:
            await ctx.send("There is no warning to delete")
        else:
            if warn not in data["warn_id"]:
                await ctx.send("Can not find that warn_id")
            else:
                if len(data["warn_id"]) == 1:
                    self.db.delete_one({"guild_id": ctx.guild.id, "user_id": target})
                else:
                    re = data["warn_id"].index(warn)
                    data["warn_id"].pop(re)
                    data["kind"].pop(re)
                    data["warner"].pop(re)
                    data["reason"].pop(re)
                    data["time"].pop(re)
                    data["addition"].pop(re)
                    self.db.update_one({"guild_id": data["guild_id"], "user_id": data["user_id"]},
                                       {"$set": {"warn_id": data["warn_id"], "kind": data["kind"],
                                                 "warner": data["warner"], "reason": data["reason"],
                                                 "time": data["time"],
                                                 "addition": data["addition"]}})
                await ctx.message.add_reaction(emoji='👍')

    @warn_menu.command(aliases=['s'])
    async def show(self, ctx: commands.Context, target: typing.Union[discord.Member, discord.User, int], page: int = 1):
        """List all the warnings the user may have"""
        if page < 1:
            return await ctx.send("Page number must be bigger than 0")
        data = self.db.find_one({"guild_id": ctx.guild.id, "user_id": target if isinstance(target, int) else target.id})
        if not data:
            await ctx.send(f"**{target}** have a clean record")
        else:
            if isinstance(target, discord.Member):
                embed = discord.Embed(
                    colour=target.colour,
                    timestamp=ctx.message.created_at
                ).set_author(icon_url=str(target.avatar_url_as(size=64)), name=f"{target} Warn List")
            elif isinstance(target, discord.User):
                embed = discord.Embed(
                    timestamp=ctx.message.created_at
                ).set_author(icon_url=str(target.avatar_url_as(size=64)), name=f"{target} Warn List")
            else:
                embed = discord.Embed(
                    timestamp=ctx.message.created_at,
                ).set_author(name=f"Warn list for user with the ID: {target}")
            line = [[], [], []]
            temp = [[], [], []]
            counter = [0, 0, 0]
            for i in range(len(data["warn_id"])):
                index = data["kind"][i]
                hold = [
                    f"**{data['warn_id'][i]}**. [`{data['time'][i]}`] __<@!{data['warner'][i]}>__ - "
                    f"{data['reason'][i]}",
                    f"**{data['warn_id'][i]}**. [`{data['time'][i]}`] - {data['reason'][i]}",
                    f"**{data['warn_id'][i]}**. [`{data['time'][i]}`] ({data['addition'][i]} mute) - "
                    f"{data['reason'][i]}"
                ]
                if counter[index] % 5 == 0 and counter[index] != 0:
                    new = "\n".join(temp[index])
                    line[index].append(new)
                    temp[index].clear()
                temp[index].append(hold[index])
                counter[index] += 1

            for i in range(len(temp)):
                new = "\n".join(temp[i])
                if new != "":
                    line[i].append(new)

            labels = ["Manual Warns", "Auto Warns", "Mutes"]
            max_page = 0
            index = 0
            for i in line:
                if len(i) > max_page:
                    max_page = len(i)
                try:
                    hold = i[page - 1]
                    if isinstance(hold, str):
                        embed.add_field(inline=False, name=labels[index], value=hold)
                except IndexError:
                    pass
                index += 1

            embed.set_footer(text=f"{page} / {max_page} Page")

            await ctx.send(embed=embed)
