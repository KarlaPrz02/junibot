import discord
from discord.ext import commands
from cogs.guild_config import get_guild_channel_id, get_guild_role_id


class JoinLeft(commands.Cog):
    """Cog para manejar eventos de entrada y salida de miembros del servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Se ejecuta cuando un miembro se une al servidor."""

        # Asignar rol si está configurado
        role_id = get_guild_role_id(member.guild.id, "member")
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    print(
                        f"[JOIN_LEFT] No se pudo asignar el rol {role_id} "
                        f"al miembro {member.id} en el servidor {member.guild.id}: "
                        "faltan permisos.",
                        flush=True,
                    )

        channel_id = get_guild_channel_id(member.guild.id, "member_join")
        if channel_id is None:
            return
        channel = await self._get_text_channel(channel_id)
        if channel:
            await channel.send(f"{member.mention} se ha unido al servidor")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Se ejecuta cuando un miembro abandona el servidor."""
        channel_id = get_guild_channel_id(member.guild.id, "member_leave")
        if channel_id is None:
            return
        channel = await self._get_text_channel(channel_id)
        if channel:
            await channel.send(f"{member.mention} ha abandonado el servidor")

    async def _get_text_channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            print(
                f"[JOIN_LEFT] El canal configurado {channel_id} no es un canal de texto.",
                flush=True,
            )
            return None
        return channel


async def setup(bot: commands.Bot):
    """Cargar el cog."""
    await bot.add_cog(JoinLeft(bot))
