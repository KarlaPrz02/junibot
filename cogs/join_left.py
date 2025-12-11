import discord
from discord.ext import commands
import json
import os

CONFIG_FILE = "config.json"

def _load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


class JoinLeft(commands.Cog):
    """Cog para manejar eventos de entrada y salida de miembros del servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = _load_config()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Se ejecuta cuando un miembro se une al servidor."""
        guild_id = str(member.guild.id)
        
        # Asignar rol si está configurado
        if guild_id in self.config:
            guild_config = self.config[guild_id]
            if isinstance(guild_config, dict):
                role_id = guild_config.get("member_role")
                if role_id and role_id > 0:
                    try:
                        role = member.guild.get_role(int(role_id))
                        if role:
                            await member.add_roles(role)
                    except discord.Forbidden:
                        pass  # Bot no tiene permisos para asignar rol
                    except Exception:
                        pass
        
        # Enviar mensaje de bienvenida
        channel_id = None
        if guild_id in self.config:
            guild_config = self.config[guild_id]
            if isinstance(guild_config, dict):
                channel_id = guild_config.get("welcome")
        
        if channel_id is None:
            for ch in member.guild.text_channels:
                if ch.permissions_for(member.guild.me).send_messages:
                    channel_id = ch.id
                    break
        
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(f"{member.mention} se ha unido al servidor")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Se ejecuta cuando un miembro abandona el servidor."""
        guild_id = str(member.guild.id)
        
        # Obtener el canal de bienvenida del config (usa el mismo para salidas)
        channel_id = None
        if guild_id in self.config:
            guild_config = self.config[guild_id]
            if isinstance(guild_config, dict):
                channel_id = guild_config.get("welcome")
        
        # Si no hay configuración, buscar el primer canal disponible
        if channel_id is None:
            for ch in member.guild.text_channels:
                if ch.permissions_for(member.guild.me).send_messages:
                    channel_id = ch.id
                    break
        
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(f"{member.mention} ha abandonado el servidor")


async def setup(bot: commands.Bot):
    """Cargar el cog."""
    await bot.add_cog(JoinLeft(bot))

