import discord as d
from discord.ext import commands, tasks
from discord import app_commands
import logging
from ..minecraft import McSrv
from ..embedUtils import createOfflineEmbed

logger = logging.getLogger('discord')

class McCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.minecraft = McSrv(bot.config.srvport)
        self.last_mc_status = None
        self.last_ip = None

    async def cog_load(self):
        logger.info("MinecraftCog loaded")
        self.last_ip = self.minecraft.getPublicIp()
        self.mcMain.start()

    async def cog_unload(self):
        logger.info("MinecraftCog unloaded")
        if self.mcMain.is_running():
            self.mcMain.cancel()
        await self.on_botOffline()

    def channelHandler(self) -> d.TextChannel | None:
        if not self.bot.config.channelID:
            logger.info("No channel has been registered for messages.")
            return None
            
        channel = self.bot.get_channel(self.bot.config.channelID)
        if channel is None:
            logger.warning(f"Channel {self.bot.config.channelID} not found. Unregistering channel.")
            self.bot.config.channelID = 0
            self.bot.config.dump()
            return None

        return channel

    def roleHandler(self) -> d.Role | None:
        if not self.bot.config.roleID:
            logger.info("No role has been set for pings.")
            return None

        role = self.bot.guild.get_role(self.bot.config.roleID)
        if role is None:
            logger.warning(f"Role {self.bot.config.roleID} not found. Unsetting role.")
            self.bot.config.roleID = 0
            self.bot.config.dump()
            return None
        
        if role > self.bot.guild.me.top_role:
            logger.warning(f"Role {role.name} ({role.id}) is too high for me to manage. Unsetting role.")
            self.bot.config.roleID = 0
            self.bot.config.dump()
            return None
        
        return role

    async def sendPing(self, channel: d.TextChannel, role: d.Role, reason: str):
        logger.info(f"Attempting to send ping for reason: {reason}")
        if self.bot.config.pingMessageID != 0:
            try:
                old_ping_message = await channel.fetch_message(self.bot.config.pingMessageID)
                await old_ping_message.delete()
                logger.debug("Deleted old ping message.")
            except d.errors.NotFound:
                logger.debug("Old ping message not found, skipping deletion.")
            except Exception as e:
                logger.error(f"Failed to delete old ping message: {e}")
        
        try:
            new_ping_message = await channel.send(role.mention)
            self.bot.config.pingMessageID = new_ping_message.id
            self.bot.config.dump()
            logger.info(f"Sent new ping message ({new_ping_message.id})")
        except Exception as e:
            logger.error(f"Failed to send new ping message: {e}")

    @app_commands.command(name="status", description="Get a live, one-time status of the Minecraft server.")
    async def status(self, interaction: d.Interaction):
        logger.info(f"/status command used by {interaction.user.name}")
        await interaction.response.defer(ephemeral=False)

        public_ip = self.minecraft.getPublicIp()
        if not public_ip:
            await interaction.followup.send("Error: Could not determine the server's public IP. Please try again later.", ephemeral=True)
            return

        live_status = self.minecraft.getServerStatus(public_ip)
        if not live_status:
            await interaction.followup.send("Error: Could not retrieve server status from the API. The server may be offline or the API is down.", ephemeral=True)
            return

        embed = self.minecraft.createStatusEmbed(live_status, public_ip)
        await interaction.followup.send(embed=embed)

    @tasks.loop(seconds=60)
    async def mcMain(self):
        channel = self.channelHandler()
        if not channel:
            if self.mcMain.is_running(): 
                self.mcMain.cancel()
            return
            
        public_ip = self.minecraft.getPublicIp()
        if not public_ip:
            logger.warning("Main loop: Could not get public IP.")
            return

        current_status = self.minecraft.getServerStatus(public_ip)
        if not current_status: 
            return

        if current_status == self.last_mc_status and public_ip == self.last_ip:
            return

        ip_changed = public_ip != self.last_ip
        online_status_changed = (not self.last_mc_status) or (current_status['online'] != self.last_mc_status['online'])
        should_ping = self.bot.config.isPing and (ip_changed or online_status_changed)

        new_embed = self.minecraft.createStatusEmbed(current_status, public_ip)
        
        try:
            message = await channel.fetch_message(self.bot.config.statusMessageID)
            await message.edit(embed=new_embed)
        except d.errors.NotFound:
            message = await channel.send(embed=new_embed)
            self.bot.config.statusMessageID = message.id
            self.bot.config.dump()

        if should_ping:
            role = self.roleHandler()
            if role:
                reason = "IP changed" if ip_changed else "Server status changed"
                await self.sendPing(channel, role, reason)

        self.last_mc_status = current_status
        self.last_ip = public_ip

    async def on_channelRegistered(self, channel: d.TextChannel):
        self.bot.config.dump()
        logger.info("New channel registered. Restarting main loop to post a new message.")
        self.mcMain.restart()

    async def on_roleRegistered(self):
        self.bot.config.dump()
        channel = self.channelHandler()
        role = self.roleHandler()
        if channel and role:
            await channel.send(f"{role.mention} was set for pings.")

    async def on_botOffline(self):
        if self.mcMain.is_running(): 
            self.mcMain.cancel()

        channel = self.channelHandler()
        if channel and self.bot.config.statusMessageID != 0:
            try:
                message = await channel.fetch_message(self.bot.config.statusMessageID)
                offline_embed = createOfflineEmbed()
                await message.edit(embed=offline_embed)
                
                if self.bot.config.isPing:
                    role = self.roleHandler()
                    if role: 
                        await self.sendPing(channel, role, "Bot shutdown")
            except d.errors.NotFound:
                pass
        
        self.bot.config.dump()

async def setup(bot):
    await bot.add_cog(McCog(bot))
