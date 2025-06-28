import urllib.request as request
import json
import logging
import os
import asyncio
import discord as d
from discord.ext import tasks
import dataclasses as dc

logging.basicConfig(format="%(asctime)s [%(levelname)s] (%(name)s): %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    handlers=[logging.FileHandler("bot.log", encoding='utf-8', mode='w'), logging.StreamHandler()],
                    level=logging.INFO)

logger = logging.getLogger('discord')

@dc.dataclass
class Config:
    token: str = ''
    adminID: int = 0
    guildID: int = 0
    srvport: int = 6969

    channelID: int = 0
    statusMessageID: int = 0
    pingMessageID: int = 0
    isPing: bool = False
    roleID: int = 0

    __filename__: str = 'botConfig.json'

    @classmethod
    def load(cls, filename: str = __filename__):
        if os.path.exists(filename):
            logger.info(f"Loading config from {filename}")
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            init_fields = {f.name for f in dc.fields(cls) if f.init}
            filtered_data = {k: v for k, v in data.items() if k in init_fields}

            obj = cls(**filtered_data)
            obj.__filename__ = filename
            logger.debug(f"Loaded config: {obj}")
            return obj
        else:
            logger.info(f"Config file {filename} not found. Returning default values.")
            obj = cls()
            obj.__filename__ = filename
            return obj


    def dump(self):
        logger.info(f"Dumping config to {self.__filename__}")
        data_to_dump = {f.name: getattr(self, f.name) for f in dc.fields(self) if f.init}
        with open(self.__filename__, 'w', encoding='utf-8') as f:
            json.dump(data_to_dump, f, indent=4)
        logger.debug(f"Dumped config: {data_to_dump}")


class Helper(d.Client):
    def __init__(self, *, intents=d.Intents.default(), config: Config):
        logger.debug("Creating client")
        self.config = config
        self.last_mc_status = None
        self.last_ip = None
        intents.guilds = True
        intents.members = True
        
        super().__init__(intents=intents)
        self.tree = d.app_commands.CommandTree(self)

    def botOwnerCheck(self, interaction: d.Interaction) -> bool:
        result = interaction.user.id == self.config.adminID
        if not result:
            interaction.response.send_message("You do not have permission to do this.", ephemeral=True)
        logger.debug(f"botOwnerCheck for user {interaction.user.name} ({interaction.user.id}) = {result}")
        return result
    
    def roleHandler(self) -> d.Role | None:
        if not self.config.roleID:
            logger.info("No role has been set for pings.")
            return None

        role = self.guild.get_role(self.config.roleID)
        if role is None:
            logger.warning(f"Role {self.config.roleID} not found. Unsetting role.")
            self.config.roleID = 0
            self.config.dump()
            return None
        
        if role > self.guild.me.top_role:
            logger.warning(f"Role {role.name} ({role.id}) is too high for me to manage. Unsetting role.")
            self.config.roleID = 0
            self.config.dump()
            return None
        
        return role
        
    def channelHandler(self) -> d.TextChannel | None:
        if not self.config.channelID:
            logger.info("No channel has been registered for messages.")
            return None
            
        channel = self.get_channel(self.config.channelID)
        if channel is None:
            logger.warning(f"Channel {self.config.channelID} not found. Unregistering channel.")
            self.config.channelID = 0
            self.config.dump()
            return None

        return channel
        
    async def sendPing(self, channel: d.TextChannel, role: d.Role, reason: str):
        logger.info(f"Attempting to send ping for reason: {reason}")
        if self.config.pingMessageID != 0:
            try:
                old_ping_message = await channel.fetch_message(self.config.pingMessageID)
                await old_ping_message.delete()
                logger.debug("Deleted old ping message.")
            except d.errors.NotFound:
                logger.debug("Old ping message not found, skipping deletion.")
            except Exception as e:
                logger.error(f"Failed to delete old ping message: {e}")
        
        try:
            new_ping_message = await channel.send(role.mention)
            self.config.pingMessageID = new_ping_message.id
            self.config.dump()
            logger.info(f"Sent new ping message ({new_ping_message.id})")
        except Exception as e:
            logger.error(f"Failed to send new ping message: {e}")

    def registerCommand(self):
        logger.debug("Setting up slash commands")
        guild_obj = d.Object(id=self.config.guildID)

        @self.tree.command(name="register", description="Register channel for the bot to send messages to.", guild=guild_obj)
        @d.app_commands.describe(channel="Channel to send messages to.")
        @d.app_commands.check(self.botOwnerCheck)
        async def register(interaction: d.Interaction, channel: d.TextChannel):
            logger.debug(f"Received /register from {interaction.user.name} for channel {channel.name}")
            old_channel_id = self.config.channelID
            old_message_id = self.config.statusMessageID
            
            if channel.id == old_channel_id:
                await interaction.response.send_message("This channel is already registered.", ephemeral=True)
                return

            if old_channel_id != 0:
                try:
                    old_channel = self.get_channel(old_channel_id) or await self.fetch_channel(old_channel_id)
                    if old_channel and old_message_id != 0:
                        old_message = await old_channel.fetch_message(old_message_id)
                        await old_message.delete()
                        logger.info(f"Deleted old status message from channel {old_channel_id}")
                except (d.errors.NotFound, d.errors.Forbidden):
                    logger.warning("Could not delete old status message. It may have been deleted already.")

            self.config.channelID = channel.id
            self.config.statusMessageID = 0
            self.config.pingMessageID = 0
            await interaction.response.send_message(f"Registered {channel.mention} for messages. Old messages will be cleaned up.")
            await self.on_channelRegistered(channel)

        @self.tree.command(name="pingtoggle", description="Toggle pinging when server comes online.", guild=guild_obj)
        @d.app_commands.check(self.botOwnerCheck)
        async def pingtoggle(interaction: d.Interaction):
            self.config.isPing = not self.config.isPing
            await interaction.response.send_message(f"Pinging is now {'enabled' if self.config.isPing else 'disabled'}.", ephemeral=True)
            self.config.dump()

        @self.tree.command(name="setpingrole", description="Set role to be pinged.", guild=guild_obj)
        @d.app_commands.describe(role="Role to be pinged.")
        @d.app_commands.check(self.botOwnerCheck)
        async def setpingrole(interaction: d.Interaction, role: d.Role):
            if role > interaction.guild.me.top_role:
                await interaction.response.send_message("Role is too high for me to manage.", ephemeral=True)
                return
            
            self.config.roleID = role.id
            await interaction.response.send_message(f"Set {role.mention} to be pinged.")
            await self.on_roleRegistered()

        @self.tree.command(name="roletoggle", description="Gain or remove the ping role.", guild=guild_obj)
        async def roletoggle(interaction: d.Interaction):
            role = self.roleHandler()
            if not role:
                await interaction.response.send_message("No ping role has been configured.", ephemeral=True)
                return
            
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"Removed {role.mention} from you.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"Added {role.mention} to you.", ephemeral=True)
        
        @self.tree.command(name="status", description="Get a live, one-time status of the Minecraft server.", guild=guild_obj)
        async def status(interaction: d.Interaction):
            logger.info(f"/status command used by {interaction.user.name}")
            await interaction.response.defer(ephemeral=False)

            public_ip = self.publicIpReq()
            if not public_ip:
                await interaction.followup.send("Error: Could not determine the server's public IP. Please try again later.", ephemeral=True)
                return

            live_status = self.mcStatusReq(public_ip)
            if not live_status:
                await interaction.followup.send("Error: Could not retrieve server status from the API. The server may be offline or the API is down.", ephemeral=True)
                return

            embed = self.createEmbed(live_status, public_ip)
            await interaction.followup.send(embed=embed)

    async def setup_hook(self): 
        logger.info("Running setup_hook")
        self.registerCommand()
        await self.tree.sync(guild=d.Object(id=self.config.guildID))
        logger.info("Slash commands synced")

    async def on_ready(self):
        logger.info(f"Bot ready as {self.user} (ID: {self.user.id})")
        
        if self.config.guildID not in [g.id for g in self.guilds]:
            logger.critical(f"Configured guildID {self.config.guildID} not found. Shutting down.")
            await self.close()
            return
            
        self.guild = self.get_guild(self.config.guildID)
        self.last_ip = self.publicIpReq()
        self.mcMain.start()

    async def on_channelRegistered(self, channel: d.TextChannel):
        self.config.dump()
        logger.info("New channel registered. Restarting main loop to post a new message.")
        self.mcMain.restart()

    async def on_roleRegistered(self):
        self.config.dump()
        channel = self.channelHandler()
        role = self.roleHandler()
        if channel and role:
            await channel.send(f"{role.mention} was set for pings.")

    def publicIpReq(self) -> str | None:
        try:
            with request.urlopen("https://api.ipify.org") as response:
                ip = response.read().decode()
                return ip
        except Exception as e:
            logger.error(f"Failed to get public IP: {e}")
            return None
        
    def mcStatusReq(self, ip_address: str) -> dict | None:
        if not ip_address:
            logger.error("mcStatusReq called without an IP address.")
            return None
        url = f"https://api.mcsrvstat.us/3/{ip_address}:{self.config.srvport}"
        req = request.Request(url, headers={'User-Agent': 'MC Status Bot'})
        try:
            with request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            logger.error(f"Failed to get Minecraft server status for {ip_address}: {e}")
            return None

    def createEmbed(self, status_data: dict, public_ip: str) -> d.Embed:
        if status_data.get('online', False):
            motd = "\n".join(status_data.get('motd', {}).get('clean', ["No MOTD."]))
            embed = d.Embed(title="Minecraft Server", description=f"```\n{motd}\n```", color=d.Color.green(), thumbnail={"url":f"https://api.mcsrvstat.us/icon/{public_ip}:{self.config.srvport}"})
            embed.add_field(name="Status", value=":green_circle: **Online**", inline=True)
            
            players_data = status_data.get('players', {})
            players_field = f"{players_data.get('online', 0)}/{players_data.get('max', 0)}"
            if 'list' in players_data:
                names = "\n".join(f"`{p['name']}`" for p in players_data['list'])
                players_field += f"\n{names}"
            embed.add_field(name="Players", value=players_field, inline=True)

            embed.add_field(name="Version", value=status_data.get('version', 'N/A'), inline=True)
            embed.add_field(name="Server Address", value=f"```\n{public_ip}:{self.config.srvport}\n```", inline=False)
        else:
            embed = d.Embed(title="Minecraft Server", description="The server is currently offline.", color=d.Color.red())
            embed.add_field(name="Status", value=":red_circle: **Offline**", inline=True)
            embed.add_field(name="Server Address", value=f"```\n{public_ip}:{self.config.srvport}\n```", inline=False)
        
        embed.set_footer(text="Status automatically updated")
        embed.timestamp = d.utils.utcnow()
        return embed

    @tasks.loop(seconds=60)
    async def mcMain(self):
        channel = self.channelHandler()
        if not channel:
            if self.mcMain.is_running(): self.mcMain.cancel()
            return
            
        public_ip = self.publicIpReq()
        if not public_ip:
            logger.warning("Main loop: Could not get public IP.")
            return

        current_status = self.mcStatusReq(public_ip)
        if not current_status: return

        if current_status == self.last_mc_status and public_ip == self.last_ip:
            return

        ip_changed = public_ip != self.last_ip
        online_status_changed = (not self.last_mc_status) or (current_status['online'] != self.last_mc_status['online'])
        should_ping = self.config.isPing and (ip_changed or online_status_changed)

        new_embed = self.createEmbed(current_status, public_ip)
        
        try:
            message = await channel.fetch_message(self.config.statusMessageID)
            await message.edit(embed=new_embed)
        except d.errors.NotFound:
            message = await channel.send(embed=new_embed)
            self.config.statusMessageID = message.id
            self.config.dump()

        if should_ping:
            role = self.roleHandler()
            if role:
                reason = "IP changed" if ip_changed else "Server status changed"
                await self.sendPing(channel, role, reason)

        self.last_mc_status = current_status
        self.last_ip = public_ip

    async def on_botOffline(self):
        if self.mcMain.is_running(): self.mcMain.cancel()

        channel = self.channelHandler()
        if channel and self.config.statusMessageID != 0:
            try:
                message = await channel.fetch_message(self.config.statusMessageID)
                offline_embed = d.Embed(title="Bot Offline", description="Status updates paused.", color=d.Color.dark_grey())
                offline_embed.timestamp = d.utils.utcnow()
                await message.edit(embed=offline_embed)
                
                if self.config.isPing:
                    role = self.roleHandler()
                    if role: await self.sendPing(channel, role, "Bot shutdown")
            except d.errors.NotFound:
                pass
        
        self.config.dump()

    async def close(self):
        await self.on_botOffline()
        await super().close()

def configInit(config: Config):
    def get(prompt: str, cast: type, default=None):
        while True:
            try:
                val = input(prompt)
                if not val and default is not None: return default
                return cast(val)
            except ValueError:
                print("Invalid input.")

    config.token = get("Enter bot token: ", str)
    config.adminID = get("Enter admin ID: ", int)
    config.guildID = get("Enter guild ID: ", int)
    config.srvport = get(f"Enter server port (default: {config.srvport}): ", int, default=config.srvport)


async def main():
    client = None
    try:
        config = Config.load()
        if not all([config.token, config.adminID, config.guildID]):
            configInit(config)
            config.dump()
        
        client = Helper(config=config)
        await client.start(config.token)
    except d.errors.LoginFailure:
        logger.error("Login failed. Check token.")
        config = Config.load(); config.token = ''; config.dump()
    except Exception:
        logger.exception("Unhandled exception during bot execution")
    finally:
        if client and not client.is_closed():
            await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown by user.")