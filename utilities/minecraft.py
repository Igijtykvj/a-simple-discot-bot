import urllib.request as request
import json
import logging
import discord as d
from .embedUtils import createStatusEmbed

logger = logging.getLogger('discord')

class McSrv:
    
    def __init__(self, srvport: int = 6969):
        self.srvport = srvport
    
    def getPublicIp(self) -> str | None:
        try:
            with request.urlopen("https://api.ipify.org") as response:
                ip = response.read().decode()
                return ip
        except Exception as e:
            logger.error(f"Failed to get public IP: {e}")
            return None

    def getServerStatus(self, ip_address: str) -> dict | None:
        if not ip_address:
            logger.error("getServerStatus called without an IP address.")
            return None
        
        url = f"https://api.mcsrvstat.us/3/{ip_address}:{self.srvport}"
        req = request.Request(url, headers={'User-Agent': 'MC Status Bot'})
        
        try:
            with request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            logger.error(f"Failed to get Minecraft server status for {ip_address}: {e}")
            return None

    def createStatusEmbed(self, status_data: dict, public_ip: str) -> d.Embed:
        if status_data.get('online', False):
            motd = "\n".join(status_data.get('motd', {}).get('clean', ["No MOTD."]))
            
            players_data = status_data.get('players', {})
            players_field = f"{players_data.get('online', 0)}/{players_data.get('max', 0)}"
            if 'list' in players_data:
                names = "\n".join(f"`{p['name']}`" for p in players_data['list'])
                players_field += f"\n{names}"
            
            fields = [
                {'name': 'Status', 'value': ':green_circle: **Online**', 'inline': True},
                {'name': 'Players', 'value': players_field, 'inline': True},
                {'name': 'Version', 'value': status_data.get('version', 'N/A'), 'inline': True},
                {'name': 'Server Address', 'value': f"```\n{public_ip}:{self.srvport}\n```", 'inline': False}
            ]
            
            return createStatusEmbed(
                title="Minecraft Server",
                description=f"```\n{motd}\n```",
                color=d.Color.green(),
                fields=fields,
                footer="Status automatically updated",
                thumbnail_url=f"https://api.mcsrvstat.us/icon/{public_ip}:{self.srvport}"
            )
        else:
            fields = [
                {'name': 'Status', 'value': ':red_circle: **Offline**', 'inline': True},
                {'name': 'Server Address', 'value': f"```\n{public_ip}:{self.srvport}\n```", 'inline': False}
            ]
            
            return createStatusEmbed(
                title="Minecraft Server",
                description="The server is currently offline.",
                color=d.Color.red(),
                fields=fields,
                footer="Status automatically updated"
            )
