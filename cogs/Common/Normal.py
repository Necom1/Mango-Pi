import discord
from discord.ext import commands

import time
import typing
import datetime
import asyncio


def verification(ver: discord.VerificationLevel):
    """
    Function that converts Verification Level type to string.

    Parameters
    ----------
    ver : discord.VerificationLevel
        discord server verification level to convert

    Returns
    -------
    str
        the converted verification level
    """
    ret = {discord.VerificationLevel.none: "Free crossing 🚶",
           discord.VerificationLevel.low: "visa? 📧",
           discord.VerificationLevel.medium: "5 minutes and older only ⌛",
           discord.VerificationLevel.high:  "Wait 10 minute, have some tea ⏲💬",
           discord.VerificationLevel.extreme: "Can I have your number? 📱"}
    return ret[ver]


class Normal(commands.Cog):
    """
    Class inherited from commands.Cog that contains normal user commands.

    Attributes
    ----------
    bot : commands.Bot
        commands.Bot reference
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor for Normal class.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference for the Cog
        """
        self.bot = bot

    # get bot connection command
    @commands.command(aliases=["connection"])
    async def ping(self, ctx: commands.Context):
        """Checks bot's Discord connection ping and process ping."""
        if self.bot.ignore_check(ctx):
            return

        # Reference: https://stackoverflow.com/questions/46307035/ping-command-with-discord-py
        before = time.monotonic()
        message = await ctx.send(":ping_pong:")
        ping = int(round((time.monotonic() - before) * 1000))
        web = int(round(self.bot.latency * 1000))
        average = int(round((ping + web) / 2))

        # default bad ping color
        c = 0xe74c3c

        if average <= 200:
            # medium ping
            c = 0xf1c40f
        if average <= 90:
            # fast ping
            c = 0x2ecc71

        embed = discord.Embed(
            title="Bot's Current Latency:",
            timestamp=ctx.message.created_at,
            colour=c)
        embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url_as(size=64))
        embed.add_field(name="Discord Ping:", value=f"{web} ms")
        embed.add_field(name="Estimated Ping: ", value=f"{ping} ms")

        await message.edit(content="", embed=embed)

    # get avatar command
    @commands.command(aliases=["pfp"])
    async def avatar(self, ctx: commands.Context, target: discord.Member = None):
        """Return the avatar of the target user."""
        if self.bot.ignore_check(ctx):
            return

        person = ctx.author if not target else target

        link = person.avatar_url
        embed = discord.Embed(
            timestamp=ctx.message.created_at,
            title=f"{person.name}'s Avatar:",
            colour=person.color,
            url=f"{link}"
        )
        embed.set_image(url=f"{link}")

        await ctx.send(embed=embed)

    @commands.command()
    async def utc(self, ctx: commands.Context):
        """Return the current UTC time."""
        if self.bot.ignore_check(ctx):
            return
        await ctx.send(datetime.datetime.utcnow().strftime("UTC Time:\n`%B %#d, %Y`\n%I:%M %p"))

    # get user info
    @commands.command(aliases=["userinfo", "uinfo"])
    async def user_info(self, ctx: commands.Context, member: typing.Union[discord.Member, discord.User, int, None]):
        """Returns information of the target user."""
        if self.bot.ignore_check(ctx):
            return

        admin = self.bot.admins.check(ctx)

        if isinstance(member, int) and admin:
            member = await self.bot.fetch_user(member)

        if isinstance(member, discord.User) and admin:
            # reference video: https://youtu.be/vV2B5cxj9kw
            embed = discord.Embed(
                colour=0x81ecec,
                timestamp=ctx.message.created_at
            )

            embed.set_author(name=f"Found User!")
            embed.set_thumbnail(url=str(member.avatar_url_as(size=256)))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url_as(size=64))

            embed.add_field(name="Name:", value=member.name, inline=False)
            embed.add_field(name="Mention:", value=member.mention, inline=False)
            embed.add_field(name="ID:", value=member.id, inline=False)
            embed.add_field(name="Joined discord on:", value=member.created_at.strftime("%#d %B %Y, %I:%M %p UTC"),
                            inline=False)

            if member.bot:
                embed.set_author(name=f"Found a Bot!")
        else:
            # reference video: https://youtu.be/vV2B5cxj9kw
            member = ctx.author if not member or \
                                   (isinstance(member, int) or isinstance(member, discord.User)) else member
            roles = [role for role in member.roles]

            embed = discord.Embed(
                colour=member.color,
                timestamp=ctx.message.created_at
            )

            embed.set_thumbnail(url=member.avatar_url_as(size=256))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url_as(size=64))

            embed.add_field(name="Mention", value=member.mention)
            embed.add_field(name="ID:", value=member.id)
            embed.add_field(name="Username", value=member)
            embed.add_field(name="Server Nickname:", value=member.display_name)

            embed.add_field(name="Joined discord on:", value=member.created_at.strftime("%#d %B %Y, %I:%M %p UTC"),
                            inline=False)
            embed.add_field(name="Joined server on:", value=member.joined_at.strftime("%#d %B %Y, %I:%M %p UTC"),
                            inline=False)

            embed.add_field(name=f"Roles ({len(roles)})", value=" ".join([role.mention for role in roles]),
                            inline=False)
            embed.add_field(name="Status", value=member.status)
            embed.add_field(name="Is on Mobile", value=member.is_on_mobile())
            if member.bot:
                embed.set_field_at(index=0, name="Bot", value=f"{member.mention}")

        await ctx.send(embed=embed)

    @commands.command(aliases=["sBanner", "sbanner", "banner"])
    @commands.guild_only()
    async def server_banner(self, ctx: commands.Context):
        """Returns the server banner if any."""
        if self.bot.ignore_check(ctx):
            return

        if not ctx.guild.banner:
            await ctx.send("This server don't have a banner 😢")
        else:
            await ctx.send(embed=discord.Embed(
                colour=0xecf0f1,
                timestamp=ctx.message.created_at,
                title=f"Server Banner for {ctx.guild}"
            ).set_image(url=ctx.guild.banner_url_as(size=2048, format='png'))
                           .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url_as(size=64)))

    @commands.command(aliases=['sicon', 'spfp'])
    @commands.guild_only()
    async def server_icon(self, ctx: commands.Context):
        """Returns the server icon."""
        if self.bot.ignore_check(ctx):
            return

        await ctx.send(embed=discord.Embed(
            colour=0xecf0f1,
            title=f"Server Icon for {ctx.guild}",
            timestamp=ctx.message.created_at
        ).set_image(url=ctx.guild.icon_url_as(static_format="png", size=1024))
                       .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url_as(size=64)))

    @commands.command(aliases=['splash', 'sSplash'])
    @commands.guild_only()
    async def server_splash(self, ctx: commands.Context):
        """Return server's join splash screen if any."""
        if self.bot.ignore_check(ctx):
            return

        if ctx.guild.splash is None:
            await ctx.send("This server don't have a invite splash screen 😢")
        else:
            await ctx.send(embed=discord.Embed(
                timestamp=ctx.message.created_at,
                colour=0xecf0f1,
                title=f"Invite Splash Screen for {ctx.guild}"
            ).set_image(url=ctx.guild.splash_url_as(size=2048, format='png'))
                    .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url_as(size=64)))

    @commands.command(aliases=["sinfo"])
    @commands.guild_only()
    async def server_info(self, ctx: commands.Context):
        """Return an embed of basic server information."""
        if self.bot.ignore_check(ctx):
            return

        server = ctx.guild
        temp = server.premium_tier

        c = 0x535c68
        if temp == 1:
            c = 0xff9ff3
        elif temp == 2:
            c = 0xf368e0
        elif temp == 3:
            c = 0xbe2edd

        normal = 0
        animated = 0
        emotes = await server.fetch_emojis()
        for i in emotes:
            if i.animated:
                animated += 1
            else:
                normal += 1

        embed = discord.Embed(
            timestamp=ctx.message.created_at,
            colour=c,
            title="𝕊𝕖𝕣𝕧𝕖𝕣 𝕀𝕟𝕗𝕠" if not server.large else "🅱🅸🅶 🆂🅴🆁🆅🅴🆁 🅸🅽🅵🅾"
        )
        embed.add_field(name="Server Name (ID)", value=f"{server.name} ({server.id})")
        embed.set_thumbnail(url=f"{server.icon_url_as(static_format='png', size=256)}")
        embed.add_field(name="Owner", value=server.get_member(server.owner_id).mention, inline=False)
        embed.add_field(name="Member Count", value=str(len(server.members)))
        embed.add_field(name="Booster Count", value=server.premium_subscription_count)
        embed.add_field(name="Region", value=server.region)
        embed.add_field(name="Filter", value=server.explicit_content_filter)
        embed.add_field(name="Security Level",
                        value=f"{verification(server.verification_level)}" + ("and need 2FA" if server.mfa_level == 1
                                                                              else ""),
                        inline=False)
        embed.add_field(name="Upload Limit", value=f"{server.filesize_limit / 1048576} MB")
        embed.add_field(name="Bitrate Limit", value=f"{server.bitrate_limit / 1000} kbps")
        embed.add_field(name="Emote Slots", value=f"{normal} / {server.emoji_limit}")
        embed.add_field(name="Animated Emote Slots", value=f"{animated} / {server.emoji_limit}")
        embed.add_field(name="Server Birthday",
                        value=server.created_at.strftime("%#d %B %Y, %I:%M %p UTC"), inline=False)

        if server.banner is not None:
            embed.set_image(url=server.banner_url_as(format='png', size=2048))

        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url_as(size=64))

        await ctx.send(embed=embed)

    @commands.command(aliases=['ei'])
    async def emote_info(self, ctx: commands.Context):
        """Sends a message for User to react and return either emote ID or str of that emote."""
        if self.bot.ignore_check(ctx):
            return

        message = await ctx.send("React to this message")

        def check(reaction1, user1):
            return reaction1.message.id == message.id and user1.id == ctx.author.id

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)
        except asyncio.TimeoutError:
            await message.edit(content="Timed out")
        else:
            if isinstance(reaction.emoji, str):
                temp = reaction.emoji
            else:
                temp = reaction.emoji.id
            await message.edit(content=f"```{temp}```")

    @commands.command(aliases=['lem'])
    @commands.guild_only()
    async def list_emotes(self, ctx: commands.Context):
        """Return an embed of server's emote list."""
        if self.bot.ignore_check(ctx):
            return
        emotes = ctx.guild.emojis
        if len(emotes) <= 0:
            await ctx.send("This server don't have any emotes.")
            return
        normal = []
        animated = []
        for i in emotes:
            if i.animated:
                animated.append(i)
            else:
                normal.append(i)
        temp = ""
        embed = discord.Embed(
            colour=0x1abc9c,
            timestamp=ctx.message.created_at
        ).set_author(icon_url=ctx.guild.icon_url, name=f"{ctx.guild.name} | Emote List")
        count = 1
        for i in normal:
            temp += f"{i} "
            if len(temp) >= 950:
                embed.add_field(name=f"Normal Emotes {count}", value=temp + " ")
                temp = ""
                count += 1
        embed.add_field(name=f"Normal Emotes {count}", value=temp + " ")
        count = 1
        temp = ""
        if len(animated) > 0:
            for i in animated:
                temp += f"{i} "
                if len(temp) >= 950:
                    embed.add_field(name=f"Animated Emotes {count}", value=temp + " ")
                    temp = ""
                    count += 1
            embed.add_field(name=f"Animated Emotes {count}", value=temp + " ")
        await ctx.send(embed=embed)

    @commands.command(aliases=["binfo"])
    async def info(self, ctx: commands.Context):
        """Returns information about this bot."""
        if self.bot.ignore_check(ctx):
            return

        embed = discord.Embed(
            colour=0x48dbfb,
            title="I am a discord bot filled with random features! I am made using Python and implements MongoDB!"
        )
        embed.set_author(name=f"Hi! I am {self.bot.user.name}!",
                         icon_url="http://icons.iconarchive.com/icons/cornmanthe3rd/plex/128/Other-python-icon.png")
        embed.set_thumbnail(url=self.bot.user.avatar_url_as(size=256))
        creator = await self.bot.fetch_user(267909205225242624)
        embed.add_field(name="Bot Master", value=self.bot.app_info.owner.mention)
        details = self.bot.admins.data['admins']
        if len(details) > 0:
            embed.add_field(name="Bot Staffs", value="\n".join(f"> {i.mention}" for i in details), inline=False)
        embed.add_field(name="Creator / Developer",
                        value=f"{creator.mention} / [Necomi#1555](https://github.com/Necom1)", inline=False)
        embed.add_field(name="I am born on", value=self.bot.user.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))
        # embed.add_field(name="Support Server", value="[Flower Field](http://discord.gg/sWYPsU7)")

        embed.set_footer(text="v 0.9 | Beta", icon_url="https://i.imgur.com/RPrw70n.jpg")

        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(Normal(bot))
    print("Load Cog:\tNormal")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("Normal")
    print("Unload Cog:\tNormal")
