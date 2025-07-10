import discord as d

def createStatusEmbed(title: str, description: str, color: d.Color, fields: list = None, footer: str = None, thumbnail_url: str = None) -> d.Embed:
    embed = d.Embed(title=title, description=description, color=color)

    if fields:
        for field in fields:
            embed.add_field(name=field['name'], value=field['value'], inline=field.get('inline', True))

    if footer:
        embed.set_footer(text=footer)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    embed.timestamp = d.utils.utcnow()
    return embed

def createOfflineEmbed(title: str = "Bot Offline", description: str = "Status updates paused.") -> d.Embed:
    return createStatusEmbed(title, description, d.Color.dark_grey())
