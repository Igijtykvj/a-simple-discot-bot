import json
import logging
import os
import dataclasses as dc

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

def configInit(config: Config):
    def get(prompt: str, cast: type, default=None):
        while True:
            try:
                val = input(prompt)
                if not val and default is not None: 
                    return default
                return cast(val)
            except ValueError:
                print("Invalid input.")

    config.token = get("Enter bot token: ", str)
    config.adminID = get("Enter admin ID: ", int)
    config.guildID = get("Enter guild ID: ", int)
    config.srvport = get(f"Enter server port (default: {config.srvport}): ", int, default=config.srvport)
