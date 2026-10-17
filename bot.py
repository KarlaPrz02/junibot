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

LANGUAGE_SETTINGS = CONFIG.setdefault("language", {
    "default": "es",
    "available": {
        "es": "Español",
        "en": "English",
    },
})
USER_LANGUAGE_PREFERENCES = CONFIG.setdefault("user_languages", {})
DEFAULT_LANGUAGE = LANGUAGE_SETTINGS.get("default", "es")
SUPPORTED_LANGUAGES = LANGUAGE_SETTINGS.get("available", {"es": "Español", "en": "English"})
LANGUAGE_DIR = os.path.join(os.path.dirname(__file__), "lang")
LANGUAGE_CACHE = {}

USER1_ID = CONFIG["users"]["user1_id"]
USER2_ID = CONFIG["users"]["user2_id"]


def _load_lang_file(lang_code: str):
    if lang_code in LANGUAGE_CACHE:
        return LANGUAGE_CACHE[lang_code]

    file_path = os.path.join(LANGUAGE_DIR, f"{lang_code}.lang")
    translations = {}
    if os.path.exists(file_path):
        section = None
        with open(file_path, "r", encoding="utf-8") as lang_file:
            for raw_line in lang_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    translations.setdefault(section, {})
                    continue
                if "=" not in line or section is None:
                    continue
                key, value = [part.strip() for part in line.split("=", 1)]
                translations[section][key] = value

    LANGUAGE_CACHE[lang_code] = translations
    return translations


def get_text_for_language(lang_code: str, section: str, key: str):
    lang_code = str(lang_code or DEFAULT_LANGUAGE).lower()
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = DEFAULT_LANGUAGE

    translations = _load_lang_file(lang_code)
    if section in translations and key in translations[section]:
        return translations[section][key]

    fallback = _load_lang_file(DEFAULT_LANGUAGE)
    if section in fallback and key in fallback[section]:
        return fallback[section][key]

    return key


def get_text_for_user(user_id, section: str, key: str):
    return get_text_for_language(get_user_language(user_id), section, key)


def save_user_languages():
    CONFIG["user_languages"] = USER_LANGUAGE_PREFERENCES
    temporary_file = "config.json.tmp"
    with open(temporary_file, "w", encoding="utf-8") as config_file:
        json.dump(CONFIG, config_file, ensure_ascii=False, indent=2)
    os.replace(temporary_file, "config.json")


def get_user_language(user_id):
    return USER_LANGUAGE_PREFERENCES.get(str(user_id), DEFAULT_LANGUAGE)


def set_user_language(user_id, language):
    normalized = str(language).lower()
    if normalized not in SUPPORTED_LANGUAGES:
        normalized = DEFAULT_LANGUAGE
    USER_LANGUAGE_PREFERENCES[str(user_id)] = normalized
    save_user_languages()
    return normalized

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
bot.user_languages = USER_LANGUAGE_PREFERENCES
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
    message = get_text_for_user(interaction.user.id, "commands", "juni_mention").format(
        user=author,
        user1=USER1_ID,
        user2=USER2_ID,
    )
    await interaction.response.send_message(message)
    
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

LANGUAGE_CHOICES = [
    app_commands.Choice(name="Español", value="es"),
    app_commands.Choice(name="English", value="en"),
]


@bot.tree.command(name="language", description="Selecciona tu idioma preferido")
@app_commands.choices(language=LANGUAGE_CHOICES)
async def language_command(interaction: discord.Interaction, language: app_commands.Choice[str]):
    selected_language = set_user_language(interaction.user.id, language.value)
    message = get_text_for_language(selected_language, "language", "success")
    await interaction.response.send_message(message, ephemeral=True)

# slash help

class HelpView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    def t(self, section: str, key: str):
        return get_text_for_user(self.user_id, section, key)

    @button(label="Ayuda General", style=discord.ButtonStyle.primary, custom_id="help_general")
    async def general(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=self.t("help", "general_title"),
            description=self.t("help", "general_description"),
            color=discord.Color.blue()
        )
        embed.add_field(name=self.t("help", "bot_prefix"), value="jb;", inline=False)
        embed.add_field(name="/juni", value=self.t("help", "juni"), inline=False)
        embed.add_field(name="/help", value=self.t("help", "help_menu"), inline=False)
        embed.add_field(name="/cumpleaños ``[add/view/delete/edit]``", value=self.t("help", "birthdays"), inline=False)
        embed.add_field(name="/recordatorio ``[add/view/delete]``", value=self.t("help", "reminders"), inline=False)
        embed.add_field(name="/configuracion", value=self.t("help", "config"), inline=False)
        embed.add_field(name="/reaccion ``[agregar/eliminar/list/limpiar]``", value=self.t("help", "reactions"), inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @button(label="Ayuda Wordle", style=discord.ButtonStyle.success, custom_id="help_wordle")
    async def wordle(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=self.t("help", "wordle_title"),
            description=self.t("help", "wordle_description"),
            color=discord.Color.green()
        )
        embed.add_field(name="/wordle ``jugar``", value=self.t("help", "wordle_start"), inline=False)
        embed.add_field(name="/wordle ``añadir`` ``<palabra>``", value=self.t("help", "wordle_add"), inline=False)
        embed.add_field(name="/intento <palabra>", value=self.t("help", "wordle_guess"), inline=False)
        embed.add_field(name="/historial", value=self.t("help", "wordle_history"), inline=False)
        embed.add_field(name="/stats", value=self.t("help", "wordle_stats"), inline=False)
        embed.add_field(name="/top", value=self.t("help", "wordle_top"), inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        
    @button(label="Ayuda recordatorios", style=discord.ButtonStyle.secondary, custom_id="help_recordatorio")
    async def recordatorio(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=self.t("help", "reminders_title"),
            description=self.t("help", "reminders_description"),
            color=discord.Color.light_gray()
        )
        embed.add_field(name=self.t("help", "reminders_what"), value=self.t("help", "reminders_what_value"), inline=False)
        embed.add_field(name=self.t("help", "usage_general"), value="/recordatorio ``[add/view/edit/delete]``", inline=False)
        embed.add_field(name=self.t("help", "usage_add"), value="/recordatorio add ``[fecha]`` ``[texto]``", inline=False)
        embed.add_field(name=self.t("help", "usage_view"), value="/recordatorio view", inline=False)
        embed.add_field(name=self.t("help", "usage_delete"), value="/recordatorio delete ``[id]``", inline=False)
        embed.add_field(name=self.t("help", "usage_edit"), value="/recordatorio edit ``[id]`` ``[fecha]`` ``[texto]``", inline=False)
        embed.add_field(name=self.t("help", "usage_quick"), value="/recordatorio add - A continuación, el bot abrirá un menu para elegir la fecha y el texto.", inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
    
    # @button(label="Ayuda Reacciones", style=discord.ButtonStyle.danger, custom_id="help_reacciones")
    # async def reacciones(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     embed = discord.Embed(
    #         title=self.t("help", "reactions_title"),
    #         description=self.t("help", "reactions_description"),
    #         color=discord.Color.red()
    #     )
    #     embed.add_field(name=self.t("help", "reactions_what"), value=self.t("help", "reactions_what_value"), inline=False)
    #     embed.add_field(name=self.t("help", "usage_general"), value="/reaccion ``[agregar/eliminar/list/limpiar]``", inline=False)
    #     embed.add_field(name=self.t("help", "reactions_add"), value="/reaccion agregar ``[mensaje_id]`` ``[emoji]`` ``[rol]``\n• mensaje_id: ID del mensaje donde se ponen las reacciones\n• emoji: El emoji a usar (ej: ❤️, 🎮)\n• rol: El rol a asignar", inline=False)
    #     embed.add_field(name=self.t("help", "reactions_delete"), value="/reaccion eliminar ``[mensaje_id]`` ``[emoji]``\nEliminará ese emoji del mensaje y la configuración.", inline=False)
    #     embed.add_field(name=self.t("help", "reactions_list"), value="/reaccion list\nMuestra todas las reacciones configuradas en el servidor.", inline=False)
    #     embed.add_field(name=self.t("help", "reactions_clean"), value="/reaccion limpiar ``[mensaje_id]``\nBorra toda la configuración de reacciones de un mensaje.", inline=False)
    #     embed.add_field(name=self.t("help", "reactions_id"), value="Haz clic derecho en el mensaje → Copiar ID del mensaje (necesita Modo Desarrollador activado).", inline=False)
    #     embed.set_footer(text="Desarrollado por KatPrz02")
    #     await interaction.message.edit(embed=embed, view=self)
    #     await interaction.response.defer()

@bot.tree.command(name="help", description="Muestra información sobre el bot")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title=get_text_for_user(interaction.user.id, "help", "title"),
        description=get_text_for_user(interaction.user.id, "help", "description"),
        color=discord.Color.blurple()
    )
    view = HelpView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

@bot.command(name="juni")
async def juni_prefix(ctx):
    author = ctx.author.mention
    await ctx.send(f"{author} mention <@{USER1_ID}> <@{USER2_ID}>")


# slash sudoku (Discord Activity)

@bot.tree.command(
    name="sudoku",
    description="Abre el Sudoku como actividad de Discord"
)
async def sudoku_slash(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "Solo disponible en servidores.",
            ephemeral=True
        )
        return

    try:
        await interaction.response.launch_activity()
    except Exception as e:
        print(f"[SUDOKU] Error lanzando Activity: {e}", flush=True)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"Error al lanzar la actividad: {e}",
                ephemeral=True
            )

# apistats
@bot.tree.command(name="apistats", description="Muestra las estadísticas de la API")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
