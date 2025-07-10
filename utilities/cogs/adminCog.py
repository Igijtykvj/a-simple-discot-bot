import discord as d
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger('discord')

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        logger.info("AdminCog loaded")

    def isBotOwner(self, interaction: d.Interaction) -> bool:
        result = interaction.user.id == self.bot.config.adminID
        if not result:
            logger.debug(f"botOwnerCheck failed for user {interaction.user.name} ({interaction.user.id})")
        return result

    @app_commands.command(name="register", description="Register channel for the bot to send messages to.")
    @app_commands.describe(channel="Channel to send messages to.")
    async def register(self, interaction: d.Interaction, channel: d.TextChannel):
        if not self.isBotOwner(interaction):
            await interaction.response.send_message("You do not have permission to do this.", ephemeral=True)
            return

        logger.debug(f"Received /register from {interaction.user.name} for channel {channel.name}")
        old_channel_id = self.bot.config.channelID
        old_message_id = self.bot.config.statusMessageID
        
        if channel.id == old_channel_id:
            await interaction.response.send_message("This channel is already registered.", ephemeral=True)
            return

        if old_channel_id != 0:
            try:
                old_channel = self.bot.get_channel(old_channel_id) or await self.bot.fetch_channel(old_channel_id)
                if old_channel and old_message_id != 0:
                    old_message = await old_channel.fetch_message(old_message_id)
                    await old_message.delete()
                    logger.info(f"Deleted old status message from channel {old_channel_id}")
            except (d.errors.NotFound, d.errors.Forbidden):
                logger.warning("Could not delete old status message. It may have been deleted already.")

        self.bot.config.channelID = channel.id
        self.bot.config.statusMessageID = 0
        self.bot.config.pingMessageID = 0
        await interaction.response.send_message(f"Registered {channel.mention} for messages. Old messages will be cleaned up.")
        
        minecraft_cog = self.bot.get_cog('MinecraftCog')
        if minecraft_cog:
            await minecraft_cog.on_channelRegistered(channel)

    @app_commands.command(name="pingtoggle", description="Toggle pinging when server comes online.")
    async def pingtoggle(self, interaction: d.Interaction):
        if not self.isBotOwner(interaction):
            await interaction.response.send_message("You do not have permission to do this.", ephemeral=True)
            return

        self.bot.config.isPing = not self.bot.config.isPing
        await interaction.response.send_message(f"Pinging is now {'enabled' if self.bot.config.isPing else 'disabled'}.", ephemeral=True)
        self.bot.config.dump()

    @app_commands.command(name="setpingrole", description="Set role to be pinged.")
    @app_commands.describe(role="Role to be pinged.")
    async def setpingrole(self, interaction: d.Interaction, role: d.Role):
        if not self.isBotOwner(interaction):
            await interaction.response.send_message("You do not have permission to do this.", ephemeral=True)
            return

        if role > interaction.guild.me.top_role:
            await interaction.response.send_message("Role is too high for me to manage.", ephemeral=True)
            return
        
        self.bot.config.roleID = role.id
        await interaction.response.send_message(f"Set {role.mention} to be pinged.")
        
        minecraft_cog = self.bot.get_cog('MinecraftCog')
        if minecraft_cog:
            await minecraft_cog.on_roleRegistered()

    @app_commands.command(name="roletoggle", description="Gain or remove the ping role.")
    async def roletoggle(self, interaction: d.Interaction):
        minecraft_cog = self.bot.get_cog('MinecraftCog')
        if not minecraft_cog:
            await interaction.response.send_message("Minecraft functionality not available.", ephemeral=True)
            return

        role = minecraft_cog.roleHandler()
        if not role:
            await interaction.response.send_message("No ping role has been configured.", ephemeral=True)
            return
        
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Removed {role.mention} from you.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Added {role.mention} to you.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
