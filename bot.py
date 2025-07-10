import asyncio
import logging
import discord as d
from discord.ext import commands
from utilities.config import Config, configInit

# Setup logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] (%(name)s): %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ],
    level=logging.INFO
)

logger = logging.getLogger('discord')

class McBot(commands.Bot):
    def __init__(self, config: Config):
        intents = d.Intents.default()
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

        self.config = config
        self.guild = None

    async def setup_hook(self):
        logger.info("Running setup_hook")

        await self.load_extension('utilities.cogs.mcCog')
        await self.load_extension('utilities.cogs.adminCog')

        guild = d.Object(id=self.config.guildID)
        await self.tree.sync(guild=guild)
        logger.info("Slash commands synced")

    async def on_ready(self):
        logger.info(f"Bot ready as {self.user} (ID: {self.user.id})")

        if self.config.guildID not in [g.id for g in self.guilds]:
            logger.critical(f"Configured guildID {self.config.guildID} not found. Shutting down.")
            await self.close()
            return

        self.guild = self.get_guild(self.config.guildID)

    async def close(self):
        logger.info("Bot shutting down...")
        await super().close()

async def main():
    client = None
    try:
        config = Config.load()
        if not all([config.token, config.adminID, config.guildID]):
            configInit(config)
            config.dump()
        
        client = McBot(config=config)
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