import typing
import discord
import asyncio
from discord.ext import commands
from Components.MangoPi import MangoPi
from Components.MuteTimer import MuteTimer, remove_mute
from Components.DelayedTask import time_converter, range_calculator


async def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog
    """
    await bot.add_cog(Mute(bot))
    print("Load Cog:\tMute")


async def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog
    """
    await bot.remove_cog("Mute")
    print("Unload Cog:\tMute")


class Mute(commands.Cog):
    """
    Class inherited from commands.Cog that contains Mute commands.

    Attributes
    ----------
    bot: MangoPi
        bot reference
    timers: dict
        dictionary containing the MuteTimers for servers
    roles: dict
        dictionary containing the mute role for servers
    role_db: MongoClient
        mongo reference to mute_role collection
    mute_db: MongoClient
        mongo reference to mute_time collection
    """

    def __init__(self, bot: MangoPi):
        """
        Constructor for the Mute class

        Parameters
        ----------
        bot: MangoPi
            pass in bot reference
        """
        self.bot = bot
        self.timers = {}
        self.roles = {}
        self.role_db = bot.mongo["mute_role"]
        self.mute_db = bot.mongo["mute_time"]
        self.update()

    def update_mute_roles(self, guild: int = None):
        """
        Method to update the roles dictionary with data from role_db. This should be executed before update_mute_timers.

        Parameters
        ----------
        guild: int
            the specific server role to update, if none then update everything
        """
        if guild:
            try:
                self.roles.pop(guild)
            except KeyError:
                pass
            data = self.role_db.find({"_id": guild})
        else:
            self.roles.clear()
            data = self.role_db.find()

        for i in data:
            server = self.bot.get_guild(i["_id"])
            if not server:
                self.role_db.delete_one({"_id": i["_id"]})
            else:
                role = server.get_role(i["role_id"])
                if not role:
                    self.role_db.delete_one({"_id": i["_id"]})
                else:
                    self.roles.update({i["_id"]: role})

    def update_mute_timers(self, guild: int = None):
        """
        Method to update the timers dictionary with data from mute_db. This should be executed after update_mute_timers.

        Parameters
        ----------
        guild: int
            the specific server timers to update, if none then update everything
        """
        late = []
        fail = []

        if guild:
            try:
                self.timers.pop(guild)
            except KeyError:
                pass
            data = self.mute_db.find({"guild_id": guild})
        else:
            self.timers.clear()
            data = self.mute_db.find()

        for i in data:
            try:
                self.roles[i["guild_id"]]
            except KeyError:
                if i["guild_id"] not in fail:
                    fail.append(i["guild_id"])
            else:
                try:
                    self.timers[i["guild_id"]]
                except KeyError:
                    self.timers.update({i["guild_id"]: {}})
                try:
                    temp = MuteTimer(self.bot, pack=i)
                except ValueError:
                    late.append(i)
                else:
                    self.timers[i["guild_id"]].update({i["user_id"]: temp})

        for i in fail:
            self.bot.mongo["mute_time"].delete_many({"guild_id": i})
            self.bot.mongo["mute_role"].delete_many({"_id": i})

        for i in late:
            asyncio.get_event_loop().create_task(remove_mute(self.bot, i["guild_id"], i["user_id"],
                                                             "Late mute removal due to Cog down time"))

    def update(self, guild: int = None):
        """
        Method used to update both timers and roles data. Meant to only be used in the constructor

        Parameters
        ----------
        guild: int
            the specific server data to update, if none then update everything
        """
        self.update_mute_roles(guild)
        self.update_mute_timers(guild)

    async def tell(self, ctx: commands.Context, target: discord.Member, reason: str, duration: str,
                   change: bool = False):
        """
        Async method that DMs the user being muted regarding their mute

        Parameters
        ----------
        ctx: commands.Context
            pass in context for reply
        target: discord.Member
            the user being muted
        reason: str
            reason for the mute
        duration: str
            when the mute will end
        change: str
            whether or not this is not a new mute
        """
        if target.bot:
            return
        if len(reason) <= 0:
            return
        if ctx.author.id == target.id:
            return

        try:
            destination = self.bot.get_cog("Warn")
            data = destination.add_warn(ctx.message.created_at, ctx.guild.id, target.id, ctx.author.id, 2, reason,
                                        duration)
        except ValueError:
            data = None

        try:
            embed = discord.Embed(timestamp=ctx.message.created_at, colour=0x636e72)
            embed.add_field(inline=False, name="End", value=duration)
            embed.add_field(inline=False, name="Reason", value=reason)
            if data:
                embed.set_footer(icon_url=target.avatar.replace(size=64).url, text=f"{data} offenses")
            embed.set_author(icon_url=ctx.guild.icon.replace(size=128).url, name=f"{ctx.guild.name}")
            await target.send("🔇 You have been muted 🔇" if not change else "➕  Mute Time Changed",
                              embed=embed)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Event listener that detects member update. If there is a manual mute role removal, remove the MuteTimer

        Parameters
        ----------
        before: discord.Member
            member data before the update
        after: discord.Member
            member data after the update
        """
        if before.roles != after.roles:
            try:
                role = self.roles[after.guild.id]
            except KeyError:
                return

            try:
                target = self.timers[after.guild.id][after.id]
            except KeyError:
                return

            if role not in after.roles:
                await target.terminate()

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: typing.Union[discord.TextChannel, discord.VoiceChannel]):
        """
        Event listener for server channel creation. Will attempt to automatically set perm for mute roles

        Parameters
        ----------
        channel: typing.Union[discord.TextChannel, discord.VoiceChannel]
            the newly created text or voice channel
        """
        try:
            data = self.roles[channel.guild.id]
        except KeyError:
            return

        try:
            if isinstance(channel, discord.TextChannel):
                await channel.set_permissions(data, send_messages=False, add_reactions=False,
                                              reason="Sync newly created text channel with mute role")
            else:
                await channel.set_permissions(data, speak=False, connect=False, use_voice_activation=False,
                                              reason="Sync newly created text channel with mute role")
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """
        Event listener for server role deletion. If the role deleted is a mute role, remove all MuteTimer associated
        with that server.

        Parameters
        ----------
        role: discord.Role
            the deleted role
        """
        try:
            data = self.roles.pop(role.guild.id)
        except KeyError:
            return

        if data.id == role.id:
            self.roles.pop(role.guild.id)
            self.role_db.delete_many({"_id": role.guild.id})
            self.mute_db.delete_manay({"guild_id": role.guild.id})
            for i in self.timers[role.guild.id]:
                await i.terminate()
            try:
                self.timers.pop(role.guild.id)
            except KeyError:
                pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """
        Event listener for when a member gets banned. This will remove the MuteTimer from that banned user if any

        Parameters
        ----------
        guild: discord.Guild
            the guild that banned the user
        user: discord.User
            the user being banned from the server
        """
        try:
            result = self.timers[guild.id][user.id]
        except KeyError:
            return

        result.terminate()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Event listener to be called when a new member joins the server. This will reapply mute role if the newly joined
        member have a MuteTimer

        Parameters
        ----------
        member: discord.Member
            the new member joining the server
        """
        try:
            self.timers[member.guild.id][member.id]
        except KeyError:
            return

        try:
            role = self.roles[member.guild.id]
        except KeyError:
            return

        await member.add_roles(role, reason="Left during a mute, time have not expired yet.")

    @commands.group(aliases=['mr'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def mute_role(self, ctx: commands.Context):
        """displays the current mute role of the server"""
        if not ctx.invoked_subcommand:
            try:
                data = self.roles[ctx.guild.id]
            except KeyError:
                await ctx.reply("This server have not set up a mute role.")
            else:
                await ctx.reply(embed=discord.Embed(
                    title="Server Mute Role",
                    colour=0x22a6b3,
                    description=f"{data.mention}",
                    timestamp=ctx.message.created_at
                ))

    @mute_role.command()
    async def set(self, ctx: commands.Context, new: discord.Role):
        """Change the mute role of the server by mention or role ID"""
        try:
            old = self.roles[ctx.guild.id]
        except KeyError:
            self.role_db.insert_one({"_id": ctx.guild.id, "role_id": new.id})
            self.roles.update({ctx.guild.id: new})
        else:
            if old.id == new.id:
                return await ctx.reply("No changes made")
            self.bot.mongo["mute_role"].update_one({"guild_id": ctx.guild.id}, {"$set": {"role_id": new.id}})
            self.roles[ctx.guild.id] = new
            try:
                data = self.timers[ctx.guild.id]
            except KeyError:
                pass
            else:
                for i in data.keys():
                    add = ctx.guild.get_member(i)
                    if add:
                        try:
                            await add.add_roles(new, reason="Update mute role - added new role")
                            await add.remove_roles(old, reason="Updated mute role - remove old role")
                        except discord.HTTPException:
                            pass

        await ctx.reply(embed=discord.Embed(
            title="Server Mute Role Updated",
            timestamp=ctx.message.created_at,
            colour=0xeccc68,
            description=f"`Updated to` {new.mention}"
        ))

    @set.error
    async def mute_role_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        Event listener for the mute_role set sub-command to reply the error back to the user.

        Parameters
        ----------
        ctx: commands.Context
            pass in context for reply
        error: commands.CommandError
            the error encountered when using the command

        Returns
        -------
        discord.Message
            the error message replied back to the user
        """
        if isinstance(error, commands.BadArgument):
            return await ctx.reply(str(error))

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx: commands.Context, target: discord.Member, time: str, *, reason: str = "Not specified"):
        """Mutes user for the specified duration"""
        if target.id == self.bot.user.id or target.id == ctx.author.id:
            return await ctx.reply("😅")
        if len(reason) > 400:
            return await ctx.reply("Too long of a ban reason... Try keep it under 400 letters...")

        try:
            time1 = time_converter(time, ctx.message.created_at)
        except ValueError as e:
            return await ctx.reply(str(e.args[0]))

        try:
            self.timers[ctx.guild.id]
        except KeyError:
            self.timers.update({ctx.guild.id: {}})

        try:
            role = self.roles[ctx.guild.id]
            if not role:
                self.mute_db.delete_many({"guild_id": ctx.guild.id})
                self.roles.pop(ctx.guild.id)
                raise KeyError()
        except KeyError:
            return await ctx.reply(f"Mute role not setup in the server. Please set it up with `{ctx.prefix}mr set "
                                   f"<role mention or ID>")

        has_role = role in target.roles
        time_str = time1.strftime('%B %#d, %Y | %I:%M %p UTC')

        try:
            data = self.timers[ctx.guild.id][target.id]
        except KeyError:
            if time.startswith("-") and not has_role:
                return await ctx.reply("User is not muted, unable to remove duration.")
            if not has_role:
                await target.add_roles(role, reason=f"Muted until {time_str} for: \n{reason}.")
            data = MuteTimer(self.bot, ctx.guild.id, target.id, time1, reason)
            self.timers[ctx.guild.id].update({target.id: data})
            self.mute_db.insert_one({"guild_id": ctx.guild.id, "user_id": target.id, "end": time1, "reason": reason})
            await ctx.reply(embed=discord.Embed(
                title="🔇 Muted",
                timestamp=ctx.message.created_at,
                colour=0x95afc0
            ).add_field(name="Member", value=target.mention).add_field(name="Duration", value=time_str, inline=False)
                           .add_field(name="Reason", value=reason, inline=False).set_thumbnail(url=target.avatar.url))
            await self.tell(ctx, target, reason, time_str)
        else:
            original = data.end
            try:
                time1 = time_converter(time, original)
            except ValueError as e:
                return await ctx.reply(str(e.args[0]))
            await data.terminate()
            try:
                data = MuteTimer(self.bot, ctx.guild.id, target.id, time1, reason)
            except ValueError:
                await target.remove_roles(role, reason=f"Mute removal after time recalculation")
                return await ctx.reply("User un-muted after time re-calculation")
            self.timers[ctx.guild.id].update({target.id: data})
            self.mute_db.update({"guild_id": ctx.guild.id, "user_id": target.id}, {
                "$set": {"end": time1, "reason": reason}
            })
            await ctx.reply(embed=discord.Embed(
                title="🔇 Mute Time Changed",
                timestamp=ctx.message.created_at,
                colour=0x95afc0
            ).add_field(name="Member", value=target.mention).add_field(name="Duration Changed To", value=time1)
                           .add_field(name="Reason", value=reason).set_thumbnail(url=target.avatar.url))
            await self.tell(ctx, target, reason, time_str, True)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx: commands.Context, target: discord.Member, *, reason: str = "No specified"):
        """Un-mutes the user if they are muted"""
        try:
            role = self.roles[ctx.guild.id]
        except KeyError:
            return await ctx.reply("Can not locate the mute role, please make sure your mute_role system is setup")

        has_role = role in target.roles
        if has_role:
            await target.remove_roles(role, reason=f"Manual mute removal with reason: \n{reason}")

        try:
            data = self.timers[ctx.guild.id][target.id]
        except KeyError:
            if has_role:
                return await ctx.reply("Mute role removed, but user not detected with a mute timer")
            else:
                return await ctx.reply("User currently don't have a mute role")
        else:
            await data.terminate()
            await ctx.message.add_reaction(emoji='🔇')

    @commands.command(aliases=['ml'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def mute_list(self, ctx: commands.Context, page: int = 1):
        """List the amount of mute timers within the server"""
        if page < 1:
            return await ctx.reply("Page number can not be less than 1")

        try:
            data = list(self.timers[ctx.guild.id].values())
            if len(data) == 0:
                raise KeyError("empty")
        except KeyError:
            return await ctx.reply("Mute list is empty")

        start, end, total = range_calculator(10, len(data), page)

        embed = discord.Embed(
            colour=0x58B19F,
            timestamp=ctx.message.created_at
        ).set_author(name="Timed Mute List", icon_url=ctx.guild.icon.replace(size=64).url)
        embed.set_footer(text=f"Page {page} / {total}")

        for i in range(start, end):
            embed.add_field(name=f"User ID: {data[i].member}",
                            value=f"<@!{data[i].member}>'s Mute Reason:\n{data[i].reason}", inline=False)

        await ctx.reply(embed=embed)
