import discord
from discord.ext import commands
import os
import json
import random
from discord import app_commands
from discord.ui import View, button
from api_client import APIClient

# Cargar configuración centralizada
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

USER1_ID = CONFIG["users"]["user1_id"]
USER2_ID = CONFIG["users"]["user2_id"]

# intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  
intents.presences = True  

class JuniBot(commands.Bot):
    async def setup_hook(self):
        for cog in CONFIG["cogs"]:
            await self.load_extension(cog)

        if self.application_id is None:
            raise RuntimeError("Discord no proporcionó el ID de la aplicación.")

        existing_commands = await self.tree._http.get_global_commands(self.application_id)
        entry_point_commands = [
            command for command in existing_commands
            if command.get("type") == 4
        ]
        command_payload = [
            command.to_dict(self.tree)
            for command in self.tree.get_commands()
        ]

        # discord.py 2.5 no modela el comando Entry Point de Activities; conservarlo
        # en la carga masiva evita que Discord lo interprete como una eliminación.
        entry_point_fields = (
            "name",
            "type",
            "description",
            "handler",
            "name_localizations",
            "description_localizations",
            "integration_types",
            "contexts",
        )
        command_payload.extend(
            {
                key: command[key]
                for key in entry_point_fields
                if key in command
            }
            for command in entry_point_commands
        )

        synced = await self.tree._http.bulk_upsert_global_commands(
            self.application_id,
            payload=command_payload,
        )
        print(f"Slash commands synced: {[command['name'] for command in synced]}")


bot = JuniBot(command_prefix=CONFIG["bot"]["prefix"], intents=intents)
bot.config = CONFIG
bot.api = APIClient(CONFIG.get("api", {}))
print("DEBUG api config:", CONFIG.get("api", {}), flush=True)
print("DEBUG bot.api creada:", bot.api, flush=True)

ACTIVITY_TYPES = {
    "watching": discord.ActivityType.watching,
    "playing": discord.ActivityType.playing,
    "listening": discord.ActivityType.listening,
    "streaming": discord.ActivityType.streaming,
}
STATUS_TYPES = {
    "online": discord.Status.online,
    "idle": discord.Status.idle,
    "dnd": discord.Status.dnd,
    "invisible": discord.Status.invisible,
}


@bot.event
async def on_ready():
    print(f"Connecting as {bot.user}...")

    activity_cfg = CONFIG["bot"]["activity"]
    activity = discord.Activity(
        type=ACTIVITY_TYPES.get(activity_cfg["type"], discord.ActivityType.watching),
        name=activity_cfg["name"]
    )
    await bot.change_presence(
        status=STATUS_TYPES.get(CONFIG["bot"]["status"], discord.Status.online),
        activity=activity
    )

    print("Bot is ready!")


# slash juni

@bot.tree.command(name="juni", description="Menciona a Juni en ambas cuentas")
async def juni_slash(interaction: discord.Interaction):
    author = interaction.user.mention
    await interaction.response.send_message(
        f"{author} mention <@{USER1_ID}> <@{USER2_ID}>"
    )
    
# Comando con prefijo: !imagen
@bot.command(name="estado", description="Envía la ruleta de los estados de juni.")
async def estado_command(ctx):
    image_path = os.path.join("assets", CONFIG["estado"]["imagen_principal"])
    with open(image_path, "rb") as f:
        file = discord.File(f, filename=CONFIG["estado"]["imagen_principal"])
        await ctx.send(file=file)

# slash estado

class EstadoGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="estado", description="Opciones relacionadas con los estados de Juni.")

    @app_commands.command(name="imagen", description="Envía la ruleta de los estados de Juni.")
    async def ruleta(self, interaction: discord.Interaction):
        await interaction.response.defer()
        image_path = os.path.join("assets", CONFIG["estado"]["imagen_principal"])
        with open(image_path, "rb") as f:
            file = discord.File(f, filename=CONFIG["estado"]["imagen_principal"])
            await interaction.followup.send(file=file)

    @app_commands.command(name="actual", description="Muestra un estado aleatorio de Juni.")
    async def actual(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_image = random.choice(CONFIG["estado"]["imagenes"])
        image_path = os.path.join("assets", selected_image)
        with open(image_path, "rb") as f:
            file = discord.File(f, filename=selected_image)
            await interaction.followup.send(file=file)
            
            
# slash carla
class carlaGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="carla", description="Opciones relacionadas con los comandos de carla.")

    @app_commands.command(name="imagen", description="Envía la ruleta de los estados de Carla.")
    async def ruleta(self, interaction: discord.Interaction):
        await interaction.response.defer()
        image_path = os.path.join("assets", CONFIG["carla"]["imagen_principal"])
        with open(image_path, "rb") as f:
            file = discord.File(f, filename=CONFIG["carla"]["imagen_principal"])
            await interaction.followup.send(file=file)

    @app_commands.command(name="actual", description="Muestra un estado aleatorio de Carla.")
    async def actual(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_image = random.choice(CONFIG["carla"]["imagenes"])
        image_path = os.path.join("assets", selected_image)
        with open(image_path, "rb") as f:
            file = discord.File(f, filename=selected_image)
            await interaction.followup.send(file=file)
            
            


# grupo de comandos 
bot.tree.add_command(EstadoGroup())
bot.tree.add_command(carlaGroup())

# slash help

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @button(label="Ayuda General", style=discord.ButtonStyle.primary, custom_id="help_general")
    async def general(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Ayuda General",
            description="Aquí tienes información general sobre los comandos del bot:",
            color=discord.Color.blue()  
        )
        embed.add_field(name="Prefijo del bot", value="jb;", inline=False)
        embed.add_field(name="/juni", value="Menciona a Juni.", inline=False)
        embed.add_field(name="/help", value="Este menú de ayuda.", inline=False)
        embed.add_field(name="/cumpleaños ``[add/view/delete/edit]``", value="Gestiona los cumpleaños.", inline=False)
        embed.add_field(name="/recordatorio ``[add/view/delete]``", value="Gestiona recordatorios.", inline=False)
        embed.add_field(name="/configuracion", value="Solo administradores: elige el ajuste que quieres ver, configurar o borrar. Para configurar un canal o rol, selecciona también el canal o rol correspondiente.", inline=False)
        embed.add_field(name="/reaccion ``[agregar/eliminar/list/limpiar]``", value="Gestiona reacciones para asignar roles.", inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer() 

    @button(label="Ayuda Wordle", style=discord.ButtonStyle.success, custom_id="help_wordle")
    async def wordle(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Ayuda Wordle",
            description="Guía para jugar al Wordle en este bot:",
            color=discord.Color.green()
        )
        embed.add_field(name="/wordle ``jugar``", value="Inicia una partida diaria de Wordle.", inline=False)
        embed.add_field(name="/wordle ``añadir`` ``<palabra>``", value="Añade una palabra al listado de Wordle.", inline=False)
        embed.add_field(name="/intento <palabra>", value="Envía un intento de 5 letras.", inline=False)
        embed.add_field(name="/historial", value="Muestra tus intentos actuales.", inline=False)
        embed.add_field(name="/stats", value="Tus estadísticas de Wordle.", inline=False)
        embed.add_field(name="/top", value="Ranking de mejores jugadores.", inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        
    @button(label="Ayuda recordatorios", style=discord.ButtonStyle.secondary, custom_id="help_recordatorio")
    async def recordatorio(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Ayuda Recordatorios",
            description="Guía para utilizar el comando recordatorios:",
            color=discord.Color.light_gray()
        )
        embed.add_field(name="¿Para que sirve?", value="Sirve para guardar un recodatorio y seleccionar cuando quieres que el bot te lo recuerde.", inline=False)
        embed.add_field(name="Uso General", value="/recordatorio ``[add/view/edit/delete]``", inline=False)
        embed.add_field(name="Uso Add", value="/recordatorio add ``[fecha]`` ``[texto]``", inline=False)
        embed.add_field(name="Uso View", value="/recordatorio view", inline=False)
        embed.add_field(name="Uso Delete", value="/recordatorio delete ``[id]``", inline=False)
        embed.add_field(name="Uso Edit", value="/recordatorio edit ``[id]`` ``[fecha]`` ``[texto]``", inline=False)
        embed.add_field(name="Uso rapido", value="/recordatorio add - A continuación, el bot abrirá un menu para elegir la fecha y el texto.", inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
    
    @button(label="Ayuda Reacciones", style=discord.ButtonStyle.danger, custom_id="help_reacciones")
    async def reacciones(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Ayuda Reacciones",
            description="Guía para utilizar el sistema de reacciones para asignar roles:",
            color=discord.Color.red()
        )
        embed.add_field(name="¿Para qué sirve?", value="Permite que usuarios obtengan roles automáticamente al reaccionar con emojis en un mensaje.", inline=False)
        embed.add_field(name="Uso General", value="/reaccion ``[agregar/eliminar/list/limpiar]``", inline=False)
        embed.add_field(name="Agregar reacción", value="/reaccion agregar ``[mensaje_id]`` ``[emoji]`` ``[rol]``\n• mensaje_id: ID del mensaje donde se ponen las reacciones\n• emoji: El emoji a usar (ej: ❤️, 🎮)\n• rol: El rol a asignar", inline=False)
        embed.add_field(name="Eliminar reacción", value="/reaccion eliminar ``[mensaje_id]`` ``[emoji]``\nEliminará ese emoji del mensaje y la configuración.", inline=False)
        embed.add_field(name="Listar reacciones", value="/reaccion list\nMuestra todas las reacciones configuradas en el servidor.", inline=False)
        embed.add_field(name="Limpiar mensaje", value="/reaccion limpiar ``[mensaje_id]``\nBorra toda la configuración de reacciones de un mensaje.", inline=False)
        embed.add_field(name="Obtener ID del mensaje", value="Haz clic derecho en el mensaje → Copiar ID del mensaje (necesita Modo Desarrollador activado).", inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

@bot.tree.command(name="help", description="Muestra información sobre el bot")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Ayuda de Juni Bot",
        description="Selecciona qué tipo de ayuda quieres",
        color=discord.Color.blurple()
    )
    view = HelpView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

@bot.command(name="juni")
async def juni_prefix(ctx):
    author = ctx.author.mention
    await ctx.send(f"{author} mention <@{USER1_ID}> <@{USER2_ID}>")


# slash sudoku (Discord Activity — misma app, ruta /sudoku)

SUDOKU_APP_ID = CONFIG.get("sudoku", {}).get("app_id", CONFIG.get("crucigrama", {}).get("app_id"))

@bot.tree.command(name="sudoku", description="Abre el Sudoku como actividad de Discord")
async def sudoku_slash(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ Solo disponible en servidores.", ephemeral=True
        )
        return

    try:
        activity_url = f"https://discord.com/activities/{SUDOKU_APP_ID}"
        embed = discord.Embed(
            title="🔢 Sudoku",
            description="¡Haz clic en el botón para jugar al Sudoku!",
            color=discord.Color.green(),
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Jugar Sudoku",
                url=activity_url,
                style=discord.ButtonStyle.link,
            )
        )
        await interaction.response.send_message(embed=embed, view=view)
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error al lanzar la actividad: {e}", ephemeral=True
        )

# apistats
@bot.tree.command(name="apistats", description="Muestra las estadísticas de la API")
async def apistats_slash(interaction: discord.Interaction):
    if not hasattr(bot, "api"):
        await interaction.response.send_message(
            "❌ La API no está configurada en el bot.",
            ephemeral=True
        )
        return

    data = await bot.api.get_stats()
    
    async def get_logs(self, limit=5, source=None):
        if not self.enabled:
            return None

        params = {"limit": limit}
        if source:
            params["source"] = source

        try:
            response = await self.client.get(f"{self.base_url}/logs", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error leyendo logs: {e}", flush=True)
            return None

    if not data:
        await interaction.response.send_message(
            "❌ No se pueden obtener las estadísticas de la API en este momento.",
            ephemeral=True
        )
        return

    total_logs = data.get("total_logs", 0)
    by_level = data.get("by_level", [])

    embed = discord.Embed(
        title="📊 Estadísticas de la API",
        color=discord.Color.blue()
    )
    embed.add_field(name="Total de logs", value=str(total_logs), inline=False)

    if by_level:
        detalle = "\n".join(
            f"• {item['level']}: {item['total']}"
            for item in by_level
        )
    else:
        detalle = "Todavía no hay logs."

    embed.add_field(name="Logs por nivel", value=detalle, inline=False)
    embed.set_footer(text="Datos leídos desde FastAPI")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
#apistats
@bot.tree.command(name="apilogs", description="Muestra los últimos logs de la API")
async def apilogs_slash(interaction: discord.Interaction, limite: int = 5):
    if not hasattr(bot, "api"):
        await interaction.response.send_message(
            "❌ La API no está configurada en el bot.",
            ephemeral=True
        )
        return

    limite = max(1, min(limite, 10))

    logs = await bot.api.get_logs(limit=limite, source="juni-bot")

    if logs is None:
        await interaction.response.send_message(
            "❌ No se pueden obtener los logs de la API en este momento.",
            ephemeral=True
        )
        return

    if not logs:
        await interaction.response.send_message(
            "ℹ️ No hay logs todavía.",
            ephemeral=True
        )
        return

    descripcion = []
    for log in logs:
        descripcion.append(
            f"**#{log['id']}** [{log['level']}] `{log['tag']}`\n"
            f"{log['message']}\n"
            f"🕒 {log['created_at']}"
        )

    embed = discord.Embed(
        title="📝 Últimos logs de JuniBot",
        description="\n\n".join(descripcion)[:4000],
        color=discord.Color.green()
    )
    embed.set_footer(text="Datos leídos desde FastAPI")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_close():
    await bot.api.close()

bot.run(CONFIG["bot"]["token"])
