import os
import shutil
import typing
import zipfile
import asyncio
import discord
import requests
from discord.ext import commands

# References:
# https://www.youtube.com/playlist?list=PLW3GfRiBCHOiEkjvQj0uaUB1Q-RckYnj9
# https://www.youtube.com/playlist?list=PLpbRB6ke-VkvP1W2d_nLa1Ott3KrDx2aN

# Resources:
# https://flatuicolors.com/
# https://discordpy.readthedocs.io/


class ModTools(commands.Cog):
    """
    Class inherited from commands.Cog that contains normal user commands.

    Attributes
    ----------
    bot : commands.Bot
        commands.Bot reference
    role : list
        command cooldown for roleall or unrole command
    instance : list
        list of server currently running download_emote command
    cooling : list
        list of server currently under 1hr cooldown of download_emote command
    """
    def __init__(self, bot: commands.Bot):
        """
        Constructor for ModTools class.

        Parameters
        ----------
        bot : commands.Bot
            pass in bot reference for the Cog
        """
        self.bot = bot
        self.role = []
        self.instance = []
        self.cooling = []

    # check if user have the permission, if so, prune
    @commands.command(aliases=["prune"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount: int, target: typing.Union[discord.Member, str] = None,
                    word: str = None):
        """Clear command to clear target amount of messages in the current channel.
        Target can either be user mention or message type (user mention, attachment, video, image)
        or message 'contain' followed by the target word. """

        # reference: https://github.com/AlexFlipnote/discord_bot.py/blob/master/cogs/mod.py
        if amount > 500:
            return await ctx.send("Please try to keep amount of messages to delete under 500, action cancelled.")
        special = " "
        if target is None:
            check = None
        elif isinstance(target, discord.Member):
            def check(m):
                return m.author == target
            special = f" **from {target}** "
        else:
            target = target.lower()
            if target not in ['embed', 'mention', 'attachments', 'attach', 'attachment', 'mentions', 'embeds',
                              'contain', 'contains', 'have', 'image', 'images', 'video', 'media']:
                return await ctx.send("Unknown operation, please check your input")

            if target in ['embed', 'embeds']:
                def check(m):
                    return len(m.embeds) > 0
                special = ' **with embeds** '
            elif target in ['attachments', 'attach', 'attachment']:
                def check(m):
                    return len(m.attachments) > 0
                special = ' **with attachments** '
            elif target in ['mention', 'mentions']:
                def check(m):
                    return (len(m.mentions) > 0) or (len(m.role_mentions) > 0)
                special = ' **with mentions** '
            elif target in ['contain', 'contains', 'have']:
                if not word:
                    await ctx.send("Please remember to input words to scan for after the operation")
                    return
                else:
                    def check(m):
                        return word.lower() in m.content.lower()
                    special = f" containing `{word.lower()}` "
            elif target in ['image', 'images']:
                def check(m):
                    if m.attachments:
                        for i in m.attachments:
                            if i.url.lower.endswith(('.jpg', '.png', '.jpeg', '.gif', '.webp', '.bmp', '.tiff')):
                                return True
                    elif m.embeds:
                        for i in m.embeds:
                            if i.image or i.thumbnail:
                                return True
                special = " **with images** "
            elif target in ['video', 'media']:
                def check(m):
                    if m.attachments:
                        for i in m.attachments:
                            if i.url.endswith(('.mp4', '.mov', '.avi', '.mkv', 'webm')):
                                return True
                    elif m.embeds:
                        for i in m.embeds:
                            if i.video:
                                return True
                special = " **with videos** "
            else:
                print(f"Error around Line 91 -> {ctx.message.content}")
                check = None
                # should never reach this point but ait
            # Possible more future prune checks

        await ctx.message.delete()
        deleted = len(await ctx.channel.purge(limit=amount, check=check))
        embed = discord.Embed(
            title="Purged! 🗑", colour=0xff6b6b,
            description=f"{deleted} messages{special}have been deleted from **{ctx.channel}**.",
            timestamp=ctx.message.created_at
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url_as(size=64))
        await ctx.send(embed=embed, delete_after=8)

    # if an error occurs when using clear command
    @clear.error
    async def clear_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        Async method called when bot experiences error from using clear command.

        Parameters
        ----------
        ctx : commands.Context
            passed in context for analysis and reply
        error : commands.CommandError
            error encountered

        Returns
        -------
        discord.Message
            processed error message sent back to context channel
        """
        nope = self.bot.ignore_check(ctx)
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("Please specify the amount to delete.", delete_after=10)
        elif isinstance(error, commands.BadArgument):
            return await ctx.send("Please enter a whole number!", delete_after=10)
        elif isinstance(error, commands.MissingPermissions):
            if nope or ctx.channel.type == discord.ChannelType.private:
                return
            embed = discord.Embed(
                title="👮 No Permission", colour=0x34ace0,
                description='You will need the permission of [Manage Messages] to use this command.'
            )
            embed.set_footer(text=f"Input by {ctx.author}", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed, delete_after=10)
        elif isinstance(error, discord.Forbidden):
            if nope:
                return
            embed = discord.Embed(
                title="😔 Not Enough Permission", colour=0xf9ca24,
                description="I don't have the permission required to perform prune. To do this, I will need: "
                            "**Manage Messages** permission."
            )
            return await ctx.send(embed=embed, delete_after=10)
        else:
            await ctx.send("Unknown error has occurred, please try again later.", delete_after=10)

    @commands.command(aliases=['ra'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def role_all(self, ctx: commands.Context, *gives: discord.Role):
        """Gives all member in the server the specified roles, 1 hour cooldown after use."""
        if ctx.guild.id in self.role:
            return await ctx.send("Command on cooldown(1hr), please try again later.")
        if len(gives) <= 0:
            return await ctx.send("Please specify the roles to give")
        self.role.append(ctx.guild.id)
        people = ctx.guild.members
        size = len(people)

        message = await ctx.send("Processing")

        count = 0
        for i in people:
            temp = False
            for k in gives:
                if k not in i.roles:
                    temp = True
                    break
            if temp:
                count += 1
                try:
                    await i.add_roles(*gives, reason=f"Add roles to all request by {ctx.author.name}")
                except discord.HTTPException:
                    await ctx.send(f"Failed to add roles to **{i}** (ID: {i.id})")

                if count % 10 == 0:
                    await message.edit(content=f"Progress: {count}/{size} added")

        await message.edit(content="Roles given to all server members")
        await asyncio.sleep(3600)
        self.role.remove(ctx.guild.id)

    @commands.command(aliases=['ua'])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def unrole_all(self, ctx: commands.Context, *removes: discord.Role):
        """Remove specific roles from all members of the server, 1 hour cooldown after use."""
        if ctx.guild.id in self.role:
            return await ctx.send("Command on cooldown(1hr), please try again later.")
        if len(removes) <= 0:
            return await ctx.send("Please specify the roles to remove")
        self.role.append(ctx.guild.id)
        people = ctx.guild.members
        size = len(people)

        message = await ctx.send("Processing")

        count = 0

        for i in people:
            temp = False
            for k in removes:
                if k in i.roles:
                    temp = True
                    break
            if temp:
                try:
                    await i.remove_roles(*removes, reason=f"Remove roles to all request by {ctx.author.name}")
                except discord.HTTPException:
                    await ctx.send(f"Failed to remove roles from **{i.name}** (ID: {i.id})")

                if count % 10 == 0:
                    await message.edit(content=f"Progress: {count}/{size} removed")

        await message.edit(content="Roles removed from all server members")
        await asyncio.sleep(3600)
        self.role.remove(ctx.guild.id)

    @commands.command(aliases=['de'])
    @commands.guild_only()
    @commands.has_permissions(manage_emojis=True)
    async def download_emote(self, ctx: commands.Context):
        """Wraps all the emotes within the server into a zipfile and upload it, 1 hour cooldown after use."""
        if ctx.guild.id in self.instance:
            return await ctx.send("This command is already running...")
        if ctx.guild.id in self.cooling:
            return await ctx.send("This command is on cooldown(1hr), please try again later.")
        emotes = ctx.guild.emojis
        if len(emotes) <= 0:
            return await ctx.send("There is no emotes in this server")
        self.instance.append(ctx.guild.id)
        # references:
        # https://stackabuse.com/creating-and-deleting-directories-with-python/
        # https://stackoverflow.com/questions/6996603/delete-a-file-or-folder

        try:
            os.makedirs(f"tmp/{ctx.guild.id}/animated")
            os.makedirs(f"tmp/{ctx.guild.id}/normal")
        except OSError:
            return await ctx.send("Error happened on line 298 of **Moderation.py**, please report this to Necomi")

        message = await ctx.send("Downloading emotes right now, going to take a while.")

        size = len(emotes)

        for i in emotes:
            r = requests.get(str(i.url), allow_redirects=True)
            if i.animated:
                path = f"tmp/{ctx.guild.id}/animated/{i.name}.gif"
            else:
                path = f"tmp/{ctx.guild.id}/normal/{i.name}.png"
            open(path, 'wb').write(r.content)

        await message.edit(content=f"{size} emotes all successfully downloaded. Zipping")

        name = f"tmp/{ctx.guild.id} - Emotes.zip"

        zipf = zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED)

        for root, dires, files in os.walk(f"tmp/{ctx.guild.id}/"):
            for file in files:
                zipf.write(os.path.join(root, file))

        zipf.close()
        await message.edit(content="File zipped, uploading...")
        await ctx.send(content=f"All the emotes for {ctx.guild.name}", file=discord.File(name))
        shutil.rmtree(f"tmp/{ctx.guild.id}/")
        await message.delete()
        os.remove(name)
        self.instance.remove(ctx.guild.id)
        self.cooling.append(ctx.guild.id)
        await asyncio.sleep(3600)
        self.cooling.remove(ctx.guild.id)


def setup(bot: commands.Bot):
    """
    Function necessary for loading Cogs.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to add Cog
    """
    bot.add_cog(ModTools(bot))
    print("Load Cog:\tModTools")


def teardown(bot: commands.Bot):
    """
    Function to be called upon unloading this Cog.

    Parameters
    ----------
    bot : commands.Bot
        pass in bot reference to remove Cog
    """
    bot.remove_cog("ModTools")
    print("Unload Cog:\tModTools")
