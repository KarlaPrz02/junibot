from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.guild_config import (
    get_guild_channel_id,
    get_guild_role_id,
    set_guild_setting,
)


CONFIGURATION_ACTIONS = [
    app_commands.Choice(name="Ver configuración", value="view"),
    app_commands.Choice(name="Canal de cumpleaños", value="birthdays"),
    app_commands.Choice(name="Canal de entradas", value="member_join"),
    app_commands.Choice(name="Canal de salidas", value="member_leave"),
    app_commands.Choice(name="Rol para nuevos miembros", value="member_role"),
    app_commands.Choice(name="Borrar canal de cumpleaños", value="clear_birthdays"),
    app_commands.Choice(name="Borrar canal de entradas", value="clear_member_join"),
    app_commands.Choice(name="Borrar canal de salidas", value="clear_member_leave"),
    app_commands.Choice(name="Borrar rol para nuevos miembros", value="clear_member_role"),
]

CHANNEL_SETTINGS = {
    "birthdays": ("birthdays", "canal de cumpleaños"),
    "member_join": ("member_join", "canal de entradas"),
    "member_leave": ("member_leave", "canal de salidas"),
}


class ServerConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_embed(self, guild: discord.Guild) -> discord.Embed:
        def channel_display(key: str) -> str:
            channel_id = get_guild_channel_id(guild.id, key)
            return f"<#{channel_id}>" if channel_id else "Sin configurar"

        role_id = get_guild_role_id(guild.id, "member")
        role_display = f"<@&{role_id}>" if role_id else "Sin configurar"
        embed = discord.Embed(
            title=f"Configuración de {guild.name}",
            description="Ajustes guardados para este servidor.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Cumpleaños", value=channel_display("birthdays"), inline=True)
        embed.add_field(name="Entradas", value=channel_display("member_join"), inline=True)
        embed.add_field(name="Salidas", value=channel_display("member_leave"), inline=True)
        embed.add_field(name="Rol para nuevos miembros", value=role_display, inline=False)
        return embed

    @app_commands.command(
        name="configuracion",
        description="Configura los canales y roles de Juni Bot en este servidor",
    )
    @app_commands.choices(ajuste=CONFIGURATION_ACTIONS)
    @app_commands.describe(
        ajuste="Qué quieres ver o configurar",
        canal="Canal de texto que quieres asignar",
        rol="Rol que quieres asignar a los nuevos miembros",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def configuracion(
        self,
        interaction: discord.Interaction,
        ajuste: app_commands.Choice[str],
        canal: Optional[discord.TextChannel] = None,
        rol: Optional[discord.Role] = None,
    ):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Este comando solo funciona en servidores.",
                ephemeral=True,
            )
            return

        action = ajuste.value
        if action == "view":
            await interaction.response.send_message(
                embed=self.make_embed(guild),
                ephemeral=True,
            )
            return

        if action in CHANNEL_SETTINGS:
            if canal is None:
                await interaction.response.send_message(
                    "Selecciona también el canal que quieres configurar.",
                    ephemeral=True,
                )
                return

            bot_member = guild.me
            if bot_member is None:
                await interaction.response.send_message(
                    "No pude comprobar los permisos del bot en este servidor.",
                    ephemeral=True,
                )
                return
            permissions = canal.permissions_for(bot_member)
            if not permissions.view_channel or not permissions.send_messages:
                await interaction.response.send_message(
                    "No puedo ver ni enviar mensajes en ese canal. Ajusta mis permisos y vuelve a intentarlo.",
                    ephemeral=True,
                )
                return

            setting_key, label = CHANNEL_SETTINGS[action]
            set_guild_setting(guild.id, "channels", setting_key, canal.id)
            await interaction.response.send_message(
                f"✅ {label.capitalize()} configurado en {canal.mention}.",
                embed=self.make_embed(guild),
                ephemeral=True,
            )
            return

        if action == "member_role":
            if rol is None:
                await interaction.response.send_message(
                    "Selecciona también el rol que quieres asignar.",
                    ephemeral=True,
                )
                return

            bot_member = guild.me
            if (
                bot_member is None
                or not bot_member.guild_permissions.manage_roles
                or rol.is_default()
                or rol >= bot_member.top_role
            ):
                await interaction.response.send_message(
                    "No puedo asignar ese rol. Comprueba que tenga permiso para gestionar roles "
                    "y que el rol esté por debajo del rol más alto del bot.",
                    ephemeral=True,
                )
                return

            set_guild_setting(guild.id, "roles", "member", rol.id)
            await interaction.response.send_message(
                f"✅ El rol para nuevos miembros se configuró como {rol.mention}.",
                embed=self.make_embed(guild),
                ephemeral=True,
            )
            return

        if action.startswith("clear_"):
            setting_key = action.removeprefix("clear_")
            if setting_key in CHANNEL_SETTINGS:
                category, key = "channels", setting_key
            elif setting_key == "member_role":
                category, key = "roles", "member"
            else:
                await interaction.response.send_message(
                    "Ese ajuste no se reconoce.",
                    ephemeral=True,
                )
                return

            set_guild_setting(guild.id, category, key, None)
            await interaction.response.send_message(
                "✅ Se borró el ajuste seleccionado.",
                embed=self.make_embed(guild),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerConfig(bot))
