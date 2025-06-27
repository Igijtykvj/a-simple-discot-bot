import urllib.request as request
import json, base64, logging, os, asyncio
import discord as d
from discord.ext import tasks
import dataclasses as dc

logging.basicConfig(format="%(asctime)s [%(levelname)s] (%(name)s): %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    handlers=[logging.FileHandler("bot.log", encoding='utf-8', mode='w'), logging.StreamHandler()],
                    level=logging.DEBUG)

logger = logging.getLogger('discord')
@dc.dataclass
class Config:
    token: str = ''
    adminID: int = 0
    guildID: int = 0

    channelID: int = 0
    isPing: bool = False
    roleID: int = 0

    __filename__: str = 'botConfig.json'

    @classmethod
    def load(cls, filename: str = __filename__):
        if os.path.exists(filename):
            logger.info(f"Loading config from {filename}")
            with open(filename, 'r') as f:
                obj = cls(**json.load(f))
                obj.__filename__ = filename
                logger.debug(f"Loaded config: {obj}")
                return obj
        else:
            logger.info(f"Config file {filename} not found. Return default values.")
            return cls()

    def dump(self, filename: str = __filename__):
        logger.info(f"Dumping config to {filename}")
        with open(filename, 'w') as f:
            json.dump(dc.asdict(self), f, indent=4)
        logger.debug(f"Dumped config: {dc.asdict(self)}")


class Helper(d.Client):
    def __init__(self, *, intents=d.Intents.default(), config: Config):
        logger.debug("Creating client")
        self.config = config

        intents.message_content = True
        intents.reactions = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = d.app_commands.CommandTree(self)

    def botOwnerCheck(self, interaction: d.Interaction):
        result = interaction.user.id == self.config.adminID
        logger.debug(f"botOwnerCheck for user {interaction.user.id} = {result}")
        return result
    
    async def setup_hook(self): 
        self.guild = self.get_guild(self.config.guildID)
        logger.debug("Setting up slash commands")
        logger.info("Running setup_hook")
        @self.tree.command(name="register", description="Register channel for the bot to send messages to.")
        @d.app_commands.describe(channel="Channel to send messages to.")
        @d.app_commands.check(self.botOwnerCheck)
        async def register(interaction: d.Interaction, channel: d.TextChannel):
            logger.debug(f"Received /register from {interaction.user} for channel {channel}")
            if channel.guild.id != self.config.guildID:
                await interaction.response.send_message(f"Channel is not in the correct guild.", ephemeral=True)
                logger.warning(f"Registered a channel that is not in the correct guild.")
                return
            if channel.id == self.config.channelID:
                await interaction.response.send_message(f"Channel is already registered.", ephemeral=True)
                logger.info(f"Registered a channel that is already registered.")
                return
            await interaction.response.send_message(f"Registered {channel.mention} for messages.")
            logger.info(f"Registered {channel.mention} for messages.")
            self.config.channelID = channel.id
            await self.on_channelRegistered(channel)

        @self.tree.command(name="pingToggle", description="Toggle pinging.")
        @d.app_commands.check(self.botOwnerCheck)
        async def pingToggle(interaction: d.Interaction):
            logger.debug(f"Received /pingToggle from {interaction.user}")
            await interaction.response.send_message(f"Pinging is now {'enabled' if not self.config.isPing else 'disabled'}.")
            logger.info(f"Toggled pinging to {'enabled' if not self.config.isPing else 'disabled'}.")
            self.config.isPing = not self.config.isPing
            await self.on_pingToggle()

        @self.tree.command(name="setPingRole", description="Set role to be pinged.")
        @d.app_commands.describe(role="Role to be pinged.")
        @d.app_commands.check(self.botOwnerCheck)
        async def setPingRole(interaction: d.Interaction, role: d.Role):
            logger.debug(f"Received /setPingRole from {interaction.user} for role {role}")
            if role > self.guild.me.top_role:
                await interaction.response.send_message(f"Role is too high for me to manage. Please set a lower role.")
                logger.warning(f"Set a role that is too high to manage.")
                return
            await interaction.response.send_message(f"Set {role.mention} to be pinged.")
            logger.info(f"Set {role.mention} to be pinged.")
            self.config.roleID = role.id
            await self.on_roleRegistered()

        @self.tree.command(name="roleToggle", description="Gain/remove ping role.")
        async def roleToggle(interaction: d.Interaction):
            logger.debug(f"Received /roleToggle from {interaction.user}")
            if not self.config.roleID:
                await interaction.response.send_message(f"Role hasn't been set yet.", ephemeral=True)
                logger.info(f"{interaction.user.name} tried to use roleToggle but no role has been set.")
                return
            
            role = self.guild.get_role(self.config.roleID)
            if role is None:
                await interaction.response.send_message(f"Role has been deleted. Unsetting role. Ask {self.get_user(self.config.adminID).mention} to set a new one.", ephemeral=True)
                logger.warning(f"{interaction.user.name} tried to use roleToggle but the role has been deleted. Deleting role config.")
                self.config.roleID = 0
                return
            if role > self.guild.me.top_role:
                await interaction.response.send_message(f"Role is too high for me to manage. Unsetting role. Ask {self.get_user(self.config.adminID).mention} to set a new one.", ephemeral=True)
                logger.warning(f"{interaction.user.name} tried to use roleToggle but the {role.name} is too high to manage. Deleting role config.")
                self.config.roleID = 0
                return
            
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"Removed {role.mention} from you.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"Added {role.mention} to you.", ephemeral=True)

        await self.tree.sync(guild=d.Object(id=self.config.guildID))

    async def on_ready(self):
        logger.info(f"Bot ready as {self.user} (ID: {self.user.id})")
        
    
    async def on_pingToggle(self):
        pass

    async def on_channelRegistered(self, channel: d.TextChannel):
        pass

    async def on_roleRegistered(self):
        pass

    def publicIpReq(self):
        logger.debug("Requesting public IP...")
        try:
            with request.urlopen("https://api.ipify.org") as response:
                ip = response.read().decode()
                logger.debug(f"Public IP: {ip}")
                return ip
        except Exception as e:
            logger.error(f"Failed to get public IP: {e}")
            return None
        
    def mcStatusReq(self):
        pass

    @tasks.loop(seconds=10)
    async def mcMain(self):
        pass

    async def on_botOffline(self):
        self.config.dump()
        pass

    async def close(self):
        logger.info("Shutting down bot...")
        await self.on_botOffline()
        await super().close()
        logger.info("Bot shutdown complete.")

def configInit(config: Config):
    logger.info("Initializing config from user input")
    def get(promt: str, cast: type):
        while True:
            try:
                return cast(input(promt))
            except ValueError:
                print("Invalid input.")

    config.token = get("Enter bot token: ", str)
    config.adminID = get("Enter admin ID: ", int)
    config.guildID = get("Enter guild ID: ", int)

async def main():
    logger.info("Bot is starting up...")
    try:
        config = Config.load()
        if not all([config.token, config.adminID, config.guildID]):
            logger.warning("Incomplete config detected. Prompting user input.")
            configInit(config)
            config.dump()
        client = Helper(config=config)
        logger.debug("Client created. Starting bot...")
        await client.start(config.token)
    except Exception as e:
        logger.exception("Unhandled exception during bot execution")
    finally:
        await client.close()

asyncio.run(main())