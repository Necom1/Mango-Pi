import time
import typing
import asyncio
import discord
import datetime
from discord.ext import commands
from Components.MangoPi import MangoPi


async def setup(bot: MangoPi):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to add Cog
    """
    await bot.add_cog(Normal(bot))
    print("Load Cog:\tNormal")


async def teardown(bot: MangoPi):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : MangoPi
        pass in bot reference to remove Cog
    """
    await bot.remove_cog("Normal")
    print("Unload Cog:\tNormal")


class Normal(commands.Cog):
    """
    Class inherited from commands.Cog that contains normal user commands.

    Attributes
    ----------
    bot : MangoPi
        MangoPi bot reference
    """
    def __init__(self, bot: MangoPi):
        """
        Constructor for Normal class.

        Parameters
        ----------
        bot : MangoPi
            pass in bot reference for the Cog
        """
        self.bot = bot
        self.verification_level = {
            discord.VerificationLevel.none: "Free crossing 🚶",
            discord.VerificationLevel.low: "visa? 📧",
            discord.VerificationLevel.medium: "5 minutes and older only ⌛",
            discord.VerificationLevel.high: "Wait 10 minute, have some tea ⏲💬",
            discord.VerificationLevel.highest: "Can I have your number? 📱"
        }

    async def cog_check(self, ctx: commands.Context):
        """
        Async method that does the command check before running

        Parameters
        ----------
        ctx: commands.Context
            pass in context to check

        Returns
        -------
        bool
            whether or not to run commands within this Cog
        """
        return not self.bot.ignore_check(ctx)

    # get bot connection command
    @commands.hybrid_command(aliases=["connection"])
    async def ping(self, ctx: commands.Context):
        """Checks bot's Discord connection ping and process ping."""
        # Reference: https://stackoverflow.com/questions/46307035/ping-command-with-discord-py
        before = time.monotonic()
        message = await ctx.reply(":ping_pong:")
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
        embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar.replace(size=64).url)
        embed.add_field(name="Discord Ping:", value=f"{web} ms")
        embed.add_field(name="Estimated Ping: ", value=f"{ping} ms")

        await message.edit(content="", embed=embed)

    # get avatar command
    @commands.command(aliases=["pfp"])
    async def avatar(self, ctx: commands.Context, target: discord.Member = None):
        """Return the avatar of the target user."""
        person = ctx.author if not target else target

        link = person.avatar.url
        embed = discord.Embed(
            timestamp=ctx.message.created_at,
            title=f"{person.name}'s Avatar:",
            colour=person.color,
            url=f"{link}"
        )
        embed.set_image(url=f"{link}")

        await ctx.reply(embed=embed)

    @commands.command()
    async def utc(self, ctx: commands.Context):
        """Return the current UTC time."""
        await ctx.reply(datetime.datetime.utcnow().strftime("UTC Time:\n`%B %#d, %Y`\n%I:%M:%S %p"))

    # get user info
    @commands.command(aliases=["userinfo", "uinfo"])
    async def user_info(self, ctx: commands.Context, member: typing.Union[discord.Member, discord.User, int, None]):
        """Returns information of the target user."""
        admin = self.bot.data.staff_check(ctx)

        if isinstance(member, int) and admin:
            member = await self.bot.fetch_user(member)

        if isinstance(member, discord.User) and admin:
            # reference video: https://youtu.be/vV2B5cxj9kw
            embed = discord.Embed(
                colour=0x81ecec,
                timestamp=ctx.message.created_at
            )

            embed.set_author(name=f"Found User!")
            embed.set_thumbnail(url=member.avatar.replace(size=256).url)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.replace(size=64).url)

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

            embed.set_thumbnail(url=member.avatar.replace(size=256).url)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.replace(size=64).url)

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

        await ctx.reply(embed=embed)

    @commands.command(aliases=["sBanner", "sbanner", "banner"])
    @commands.guild_only()
    async def server_banner(self, ctx: commands.Context):
        """Returns the server banner if any."""
        if not ctx.guild.banner:
            await ctx.reply("This server don't have a banner 😢")
        else:
            await ctx.reply(embed=discord.Embed(
                colour=0xecf0f1,
                timestamp=ctx.message.created_at,
                title=f"Server Banner for {ctx.guild}"
            ).set_image(url=ctx.guild.banner.replace(size=2048, format='png').url)
                           .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.replace(size=64).url))

    @commands.command(aliases=['sicon', 'spfp'])
    @commands.guild_only()
    async def server_icon(self, ctx: commands.Context):
        """Returns the server icon."""
        await ctx.reply(embed=discord.Embed(
            colour=0xecf0f1,
            title=f"Server Icon for {ctx.guild}",
            timestamp=ctx.message.created_at
        ).set_image(url=ctx.guild.icon.replace(size=1024).url)
                       .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.replace(size=64).url))

    @commands.command(aliases=['splash', 'sSplash'])
    @commands.guild_only()
    async def server_splash(self, ctx: commands.Context):
        """Return server's join splash screen if any."""
        if ctx.guild.splash is None:
            await ctx.reply("This server don't have a invite splash screen 😢")
        else:
            await ctx.reply(embed=discord.Embed(
                timestamp=ctx.message.created_at,
                colour=0xecf0f1,
                title=f"Invite Splash Screen for {ctx.guild}"
            ).set_image(url=ctx.guild.splash.replace(size=2048, format='png').url)
                    .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.replace(size=64).url))

    @commands.command(aliases=["sinfo"])
    @commands.guild_only()
    async def server_info(self, ctx: commands.Context):
        """Return an embed of basic server information."""
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
        embed.set_thumbnail(url=f"{server.icon.replace(static_format='png', size=256).url}")
        embed.add_field(name="Owner", value=server.get_member(server.owner_id).mention, inline=False)
        embed.add_field(name="Member Count", value=str(len(server.members)))
        embed.add_field(name="Booster Count", value=server.premium_subscription_count)
        embed.add_field(name="Filter", value=server.explicit_content_filter)
        embed.add_field(name="Security Level",
                        value=f"{self.verification_level[server.verification_level]}" +
                              ("and need 2FA" if server.mfa_level == 1 else ""),
                        inline=False)
        embed.add_field(name="Upload Limit", value=f"{server.filesize_limit / 1048576} MB")
        embed.add_field(name="Bit Rate Limit", value=f"{server.bitrate_limit / 1000} kbps")
        embed.add_field(name="Emote Slots", value=f"{normal} / {server.emoji_limit}")
        embed.add_field(name="Animated Emote Slots", value=f"{animated} / {server.emoji_limit}")
        embed.add_field(name="Server Birthday",
                        value=server.created_at.strftime("%#d %B %Y, %I:%M %p UTC"), inline=False)

        if server.banner is not None:
            embed.set_image(url=server.banner.replace(format='png', size=2048).url)

        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.replace(size=64).url)

        await ctx.reply(embed=embed)

    @commands.command(aliases=['ei'])
    async def emote_info(self, ctx: commands.Context):
        """Sends a message for User to react and return either emote ID or str of that emote."""
        message = await ctx.reply("React to this message")

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
        emotes = ctx.guild.emojis
        if len(emotes) <= 0:
            return await ctx.reply("This server don't have any emotes.")

        normal = []
        animated = []
        for i in emotes:
            if i.animated:
                animated.append(i)
            else:
                normal.append(i)

        original = discord.Embed(
            colour=0x1abc9c,
            timestamp=ctx.message.created_at
        ).set_author(icon_url=ctx.guild.icon.replace(size=128, static_format="png").url, name=f"{ctx.guild.name} | Emote List")

        send = []

        for v in ((normal, "Normal"), (animated, "Animated")):
            embed = original.copy()
            if len(v[0]) > 0:
                count = 1
                temp = ""
                for i in v[0]:
                    temp += f"{i} "
                    if len(embed) > 5000:
                        send.append(embed.copy())
                        embed = original.copy()
                    if len(temp) >= 950:
                        embed.add_field(name=f"{v[1]} Emotes {count}", value=temp + " ")
                        temp = ""
                        count += 1
                if temp != "":
                    embed.add_field(name=f"{v[1]} Emotes {count}", value=temp + " ")
                send.append(embed.copy())

        for i in send:
            await ctx.reply(embed=i)

    @commands.command(aliases=["binfo"])
    async def info(self, ctx: commands.Context):
        """Returns information about this bot."""
        embed = discord.Embed(
            colour=0x48dbfb,
            title="I am a discord bot filled with random features! I am made using Pycord and MongoDB!"
        )
        embed.set_author(name=f"Hi! I am {self.bot.user.name}!",
                         icon_url="https://icons.iconarchive.com/icons/cornmanthe3rd/plex/128/Other-python-icon.png")
        embed.set_thumbnail(url=self.bot.user.avatar.replace(size=256).url)
        creator = await self.bot.fetch_user(267909205225242624)
        embed.add_field(name="Bot Master", value=self.bot.app_info.owner.mention)
        details = self.bot.data.staff
        if len(details) > 0:
            embed.add_field(name="Bot Staffs", value="\n".join(f"> <@!{i}>" for i in details), inline=False)
        embed.add_field(name="Creator / Developer",
                        value=f"{creator.mention} / [Necom1](https://github.com/Necom1)", inline=False)
        embed.add_field(name="I am born on", value=self.bot.user.created_at.strftime("%#d %B %Y, %I:%M %p UTC"))

        embed.set_footer(text="v 1.2", icon_url="https://i.imgur.com/RPrw70n.jpg")

        await ctx.reply(embed=embed)
