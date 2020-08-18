import discord
from pymongo import MongoClient
from discord.ext import commands


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
