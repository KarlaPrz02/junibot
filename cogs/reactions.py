import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from typing import Optional

DATA_FILE = "reactions.json"

def cargar_reacciones():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_reacciones(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or payload.guild_id is None:
            return
        
        reacciones = cargar_reacciones()
        guild_id = str(payload.guild_id)
        message_id = str(payload.message_id)
        
        if guild_id not in reacciones or message_id not in reacciones[guild_id]:
            return
        
        emoji_str = str(payload.emoji)
        if emoji_str not in reacciones[guild_id][message_id]:
            return
        
        role_id = int(reacciones[guild_id][message_id][emoji_str])
        
        try:
            guild = self.bot.get_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)
            role = guild.get_role(role_id)
            if role:
                await member.add_roles(role)
        except Exception as e:
            print(f"Error al asignar rol: {e}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or payload.guild_id is None:
            return
        
        reacciones = cargar_reacciones()
        guild_id = str(payload.guild_id)
        message_id = str(payload.message_id)
        
        if guild_id not in reacciones or message_id not in reacciones[guild_id]:
            return
        
        emoji_str = str(payload.emoji)
        if emoji_str not in reacciones[guild_id][message_id]:
            return
        
        role_id = int(reacciones[guild_id][message_id][emoji_str])
        
        try:
            guild = self.bot.get_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)
            role = guild.get_role(role_id)
            if role:
                await member.remove_roles(role)
        except Exception as e:
            print(f"Error al eliminar rol: {e}")
    
    @app_commands.command(
        name="reaccion",
        description="Sistema de reacciones para asignar roles"
    )
    @app_commands.describe(
        accion="Qué acción deseas realizar",
        mensaje_id="ID del mensaje",
        emoji="Emoji a usar",
        rol="Rol a asignar"
    )
    @app_commands.choices(accion=[
        app_commands.Choice(name="Agregar", value="agregar"),
        app_commands.Choice(name="Eliminar", value="eliminar"),
        app_commands.Choice(name="Listar", value="list"),
        app_commands.Choice(name="Limpiar mensaje", value="limpiar")
    ])
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reaccion(
        self,
        interaction: discord.Interaction,
        accion: str,
        mensaje_id: Optional[str] = None,
        emoji: Optional[str] = None,
        rol: Optional[discord.Role] = None
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "Este comando solo funciona en servidores.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        reacciones = cargar_reacciones()
        guild_id = str(interaction.guild_id)

        # -------- LISTAR --------
        if accion == "list":
            if guild_id not in reacciones or not reacciones[guild_id]:
                await interaction.followup.send(
                    "No hay reacciones configuradas en este servidor."
                )
                return

            embed = discord.Embed(
                title="Reacciones configuradas",
                color=discord.Color.blue()
            )

            for msg_id, emojis in reacciones[guild_id].items():
                texto = ""
                for emoji_item, role_id in emojis.items():
                    role = interaction.guild.get_role(int(role_id))
                    role_name = role.mention if role else f"Rol desconocido ({role_id})"
                    texto += f"{emoji_item} → {role_name}\n"

                embed.add_field(
                    name=f"Mensaje: {msg_id}",
                    value=texto,
                    inline=False
                )

            await interaction.followup.send(embed=embed)
            return

        # Validar mensaje
        if not mensaje_id:
            await interaction.followup.send("Debes proporcionar el ID del mensaje.")
            return

        try:
            msg_id = int(mensaje_id)
        except ValueError:
            await interaction.followup.send("El ID debe ser numérico.")
            return

        message_id_str = str(msg_id)

        # Buscar mensaje
        message = None
        try:
            message = await interaction.channel.fetch_message(msg_id)
        except:
            for channel in interaction.guild.text_channels:
                try:
                    message = await channel.fetch_message(msg_id)
                    break
                except:
                    continue

        # -------- AGREGAR --------
        if accion == "agregar":
            if not emoji or not rol:
                await interaction.followup.send(
                    "Necesitas emoji y rol para agregar."
                )
                return

            if guild_id not in reacciones:
                reacciones[guild_id] = {}
            if message_id_str not in reacciones[guild_id]:
                reacciones[guild_id][message_id_str] = {}

            emoji_str = emoji.strip()
            reacciones[guild_id][message_id_str][emoji_str] = str(rol.id)
            guardar_reacciones(reacciones)

            if message:
                try:
                    await message.add_reaction(emoji_str)
                except:
                    pass

            await interaction.followup.send(
                f"Configurado: {emoji_str} → {rol.mention}"
            )

        # -------- ELIMINAR --------
        elif accion == "eliminar":
            if not emoji:
                await interaction.followup.send(
                    "Debes indicar el emoji a eliminar."
                )
                return

            emoji_str = emoji.strip()

            if (guild_id not in reacciones or
                message_id_str not in reacciones[guild_id] or
                emoji_str not in reacciones[guild_id][message_id_str]):
                await interaction.followup.send(
                    "Esa reacción no está configurada."
                )
                return

            del reacciones[guild_id][message_id_str][emoji_str]

            if not reacciones[guild_id][message_id_str]:
                del reacciones[guild_id][message_id_str]
            if not reacciones[guild_id]:
                del reacciones[guild_id]

            guardar_reacciones(reacciones)

            if message:
                try:
                    await message.clear_reaction(emoji_str)
                except:
                    pass

            await interaction.followup.send(
                f"Reacción eliminada: {emoji_str}"
            )

        # -------- LIMPIAR --------
        elif accion == "limpiar":
            if guild_id not in reacciones or message_id_str not in reacciones[guild_id]:
                await interaction.followup.send(
                    "Ese mensaje no tiene configuración."
                )
                return

            del reacciones[guild_id][message_id_str]

            if not reacciones[guild_id]:
                del reacciones[guild_id]

            guardar_reacciones(reacciones)

            if message:
                try:
                    await message.clear_reactions()
                except:
                    pass

            await interaction.followup.send(
                f"Configuración del mensaje {mensaje_id} eliminada."
            )

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))

