import discord
from discord.ext import commands
import os
from discord import app_commands
import random
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from discord.ui import View, button

active_games = {}

palabras_diarias = []
FECHA_INICIO = datetime(2025, 6, 6, tzinfo=ZoneInfo("Europe/Madrid")).date()

def obtener_palabra_del_dia():
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
    dias_transcurridos = (hoy - FECHA_INICIO).days
    return palabras_diarias[dias_transcurridos % len(palabras_diarias)]



USER1_ID = 485273034295607297
USER2_ID = 1303027527799013458

# intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  
intents.presences = True  

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    
    cargar_stats()
    cargar_palabras()

    print(f"Connecting as {bot.user}...")

    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"Error sync commands: {e}")

    activity = discord.Activity(type=discord.ActivityType.watching, name="Juni")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    print("Bot is ready!")


# class de boton de jugar

class JugarWordleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Jugar", style=discord.ButtonStyle.primary, custom_id="jugar_wordle")
    async def jugar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await iniciar_wordle(interaction)  


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
    image_path = os.path.join("assets", "image.png")
    with open(image_path, "rb") as f:
        file = discord.File(f, filename="image.png")
        await ctx.send(file=file)

# slash estado

class EstadoGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="estado", description="Opciones relacionadas con los estados de Juni.")

    @app_commands.command(name="imagen", description="Envía la ruleta de los estados de Juni.")
    async def ruleta(self, interaction: discord.Interaction):
        await interaction.response.defer()
        image_path = os.path.join("assets", "image.png")
        with open(image_path, "rb") as f:
            file = discord.File(f, filename="image.png")
            await interaction.followup.send(file=file)

    @app_commands.command(name="actual", description="Muestra un estado aleatorio de Juni.")
    async def actual(self, interaction: discord.Interaction):
        await interaction.response.defer()
        image_files = ["estado1.PNG", "estado2.PNG", "estado3.PNG", "estado4.PNG"]
        selected_image = random.choice(image_files)
        image_path = os.path.join("assets", selected_image)
        with open(image_path, "rb") as f:
            file = discord.File(f, filename=selected_image)
            await interaction.followup.send(file=file)
            
            


# grupo de comandos 
bot.tree.add_command(EstadoGroup())

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
        embed.add_field(name="/juni", value="Menciona a Juni.", inline=False)
        embed.add_field(name="/help", value="Este menú de ayuda.", inline=False)
        embed.add_field(name="/estado", value="Muestra los estados de Juni.", inline=False)
        embed.set_footer(text="Desarrollado por KatPrz02")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()  # evita el error "This interaction has already been responded to"

    @button(label="Ayuda Wordle", style=discord.ButtonStyle.success, custom_id="help_wordle")
    async def wordle(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Ayuda Wordle",
            description="Guía para jugar al Wordle en este bot:",
            color=discord.Color.green()
        )
        embed.add_field(name="/wordle", value="Inicia una partida diaria de Wordle.", inline=False)
        embed.add_field(name="/intento <palabra>", value="Envía un intento de 5 letras.", inline=False)
        embed.add_field(name="/historial", value="Muestra tus intentos actuales.", inline=False)
        embed.add_field(name="/stats", value="Tus estadísticas de Wordle.", inline=False)
        embed.add_field(name="/top", value="Ranking de mejores jugadores.", inline=False)
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

# WORDLE

from typing import Dict  # noqa: E402

# Partidas activas por usuario
active_games: Dict[int, Dict] = {}
ended_games: Dict[int, Dict] = {}


ultima_fecha = datetime.now(ZoneInfo("Europe/Madrid")).date()



# Estadísticas por usuario
user_stats = {}
user_stats: Dict[int, Dict[str, int]] = {}

def feedback(palabra_objetivo, intento):
    colores = ["⬜"] * 5
    objetivo_restante = list(palabra_objetivo)
    usados = [False] * 5

    for i in range(5):
        if intento[i] == palabra_objetivo[i]:
            colores[i] = "🟩"
            objetivo_restante[i] = None
            usados[i] = True

    for i in range(5):
        if not usados[i] and intento[i] in objetivo_restante:
            colores[i] = "🟨"
            objetivo_restante[objetivo_restante.index(intento[i])] = None

    letras = " ".join(intento.upper())
    resultado = "".join(colores)

    return letras, resultado

# slash wordle

@bot.tree.command(name="wordle", description="Inicia una partida de Wordle en español")
async def wordle_slash(interaction: discord.Interaction):
    limpiar_cache_si_cambio_dia()
    user_id = interaction.user.id
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()

    stats = user_stats.get(user_id, {})
    ultima = stats.get("ultima_partida")

    if ultima == hoy:
        await interaction.response.send_message("🕒 Ya jugaste al Wordle hoy. Podrás jugar de nuevo mañana.", ephemeral=True)
        return

    if user_id in active_games:
        await interaction.response.send_message("❗ Ya tienes una partida activa. Usa `/intento` para continuar.", ephemeral=True)
        return

    try:
        with open("palabras.txt", encoding="utf-8") as f:
            lista_palabras = [line.strip().lower() for line in f if len(line.strip()) == 5]
    except FileNotFoundError:
        await interaction.response.send_message("❌ No se encontró el archivo `palabras.txt`.", ephemeral=True)
        return

    if not lista_palabras:
        await interaction.response.send_message("⚠️ El archivo `palabras.txt` está vacío o mal formateado.", ephemeral=True)
        return

    palabra_objetivo = obtener_palabra_del_dia()
    active_games[user_id] = {
        "palabra": palabra_objetivo,
        "intentos": 0,
        "historial": [],
        "canal_id": interaction.channel.id
    }

    await interaction.response.send_message(
        "🎮 ¡Partida iniciada! Usa `/intento palabra:<palabra>` para jugar.",
        ephemeral=True
    )
    

# slash intento

@bot.tree.command(name="intento", description="Envía un intento para el Wordle en curso")
@app_commands.describe(palabra="Tu intento de 5 letras")
async def intento_slash(interaction: discord.Interaction, palabra: str):
    limpiar_cache_si_cambio_dia()
    user_id = interaction.user.id
    palabra = palabra.lower().strip()

    if user_id not in active_games:
        await interaction.response.send_message("❌ No tienes una partida activa. Usa `/wordle` para empezar.", ephemeral=True)
        return

    if len(palabra) != 5 or not palabra.isalpha():
        await interaction.response.send_message("❌ La palabra debe tener exactamente 5 letras.", ephemeral=True)
        return
    

    partida = active_games[user_id]
    palabra_objetivo = partida["palabra"]
    partida["intentos"] += 1

    letras, colores = feedback(palabra_objetivo, palabra)
    partida["historial"].append((letras, colores))

    canal = bot.get_channel(partida["canal_id"])
    nombre_usuario = interaction.user.display_name

    embed = discord.Embed(
        title=f"Wordle — Intento {partida['intentos']} de 6",
        color=discord.Color.orange()
    )
    embed.add_field(name="Tu intento", value=f"{letras}\n{colores}", inline=False)

    grid = "\n".join(f"{l}\n{c}" for l, c in partida["historial"])
    embed.add_field(name="Historial", value=f"```{grid}```", inline=False)

    intentos_restantes = 6 - partida["intentos"]
    embed.set_footer(text=f"{intentos_restantes} intento(s) restante(s)" if intentos_restantes else "Último intento")

    await interaction.response.send_message(embed=embed, ephemeral=True)

    if palabra == palabra_objetivo:
        mensaje_publico = f"✅ **{nombre_usuario}** adivinó la palabra en {partida['intentos']} intento(s).\n"
        grid = "\n".join(r for _, r in partida["historial"])
        mensaje_publico += "\n" + f"```{grid}```" + "\n"
        actualizar_stats(user_id, victoria=True)
        await canal.send(mensaje_publico, view=JugarWordleView())
        ended_games[user_id] = partida  # Mover a partidas finalizadas
        del active_games[user_id]

    elif partida["intentos"] >= 6:
        mensaje_publico = f"❌ **{nombre_usuario}** no adivinó la palabra en 6 intentos.\n"
        grid = "\n".join(r for _, r in partida["historial"])
        mensaje_publico += "\n" + f"```{grid}```" + "\n"
        actualizar_stats(user_id, victoria=False)
        await canal.send(mensaje_publico, view=JugarWordleView())
        ended_games[user_id] = partida  # Mover a partidas finalizadas
        del active_games[user_id]
        
def limpiar_cache_si_cambio_dia():
    global ultima_fecha, active_games
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
    if hoy != ultima_fecha:
        active_games.clear()
        ultima_fecha = hoy



# slash stats
    
@bot.tree.command(name="stats", description="Muestra tus estadísticas de Wordle")
async def stats_slash(interaction: discord.Interaction):
    user_id = interaction.user.id
    stats = user_stats.get(user_id, {"victorias": 0, "derrotas": 0})

    embed = discord.Embed(
        title=f"Estadísticas de {interaction.user.display_name}",
        color=discord.Color.green()
    )
    embed.add_field(name="Victorias", value=str(stats["victorias"]), inline=True)
    embed.add_field(name="Derrotas", value=str(stats["derrotas"]), inline=True)
    embed.set_footer(text="¡Sigue jugando para mejorar tus resultados!")
    
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Ver stats online", url="https://karlaprz02.github.io/wordle/"))

    await interaction.response.send_message(embed=embed, ephemeral=True, view=view)



    
# json file


STATS_FILE = "stats.json"

def guardar_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_stats, f, ensure_ascii=False, indent=4)

def cargar_stats():
    global user_stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                data = json.loads(contenido) if contenido else {}
                user_stats = {int(k): v for k, v in data.items()}
        except (json.JSONDecodeError, IOError):
            print("⚠️ El archivo stats.json está vacío o corrupto. Se reinician las estadísticas.")
            user_stats = {}
    else:
        user_stats = {}

        
def cargar_palabras():
    print("Cargando palabras...")
    global palabras_diarias
    try:
        with open("palabras.txt", encoding="utf-8") as f:
            palabras_diarias = [line.strip().lower() for line in f if len(line.strip()) == 5]
    except FileNotFoundError:
        print("❌ No se encontró 'palabras.txt'")
        palabras_diarias = []

    print(f"Palabras cargadas: {len(palabras_diarias)}")
        
def obtener_palabra_del_dia():
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
    dias_transcurridos = (hoy - FECHA_INICIO).days
    if dias_transcurridos < len(palabras_diarias):
        return palabras_diarias[dias_transcurridos]
    else:
        # Si se termina la lista vuelve al inicio 
        return palabras_diarias[dias_transcurridos % len(palabras_diarias)]



def actualizar_stats(user_id: int, victoria: bool):
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    user_stats.setdefault(user_id, {"victorias": 0, "derrotas": 0, "ultima_partida": ""})
    if victoria:
        user_stats[user_id]["victorias"] += 1
    else:
        user_stats[user_id]["derrotas"] += 1
    user_stats[user_id]["ultima_partida"] = hoy
    guardar_stats()
    
# slash top

    
@bot.tree.command(name="top", description="Muestra el ranking de jugadores de Wordle")
async def top_slash(interaction: discord.Interaction):
    if not user_stats:
        await interaction.response.send_message("📊 No hay estadísticas registradas todavía.", ephemeral=True)
        return

    # victorias descendente, luego derrotas ascendente
    ranking = sorted(user_stats.items(), key=lambda item: (item[1]["victorias"], -item[1]["derrotas"]), reverse=True)

    embed = discord.Embed(
        title="🏆 Ranking de Wordle",
        description="Top 10 jugadores con más victorias",
        color=discord.Color.gold()
    )

    for i, (user_id, stats) in enumerate(ranking[:10]):
        user = await bot.fetch_user(int(user_id))
        nombre = user.display_name if user else f"Usuario {user_id}"
        embed.add_field(
            name=f"{i+1}. {nombre}",
            value=f"✅ Victorias: {stats['victorias']} | ❌ Derrotas: {stats['derrotas']}",
            inline=False
        )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Ver stats online", url="https://karlaprz02.github.io/wordle/"))

    await interaction.response.send_message(embed=embed, view=view)


    

    
async def iniciar_wordle(interaction: discord.Interaction):
    limpiar_cache_si_cambio_dia()
    user_id = interaction.user.id
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()

    stats = user_stats.get(user_id, {})
    ultima = stats.get("ultima_partida")

    if ultima == hoy:
        await interaction.response.send_message("🕒 Ya jugaste al Wordle hoy. Podrás jugar de nuevo mañana.", ephemeral=True)
        return

    if user_id in active_games:
        await interaction.response.send_message("❗ Ya tienes una partida activa. Usa `/intento` para continuar.", ephemeral=True)
        return

    try:
        with open("palabras.txt", encoding="utf-8") as f:
            lista_palabras = [line.strip().lower() for line in f if len(line.strip()) == 5]
    except FileNotFoundError:
        await interaction.response.send_message("❌ No se encontró el archivo `palabras.txt`.", ephemeral=True)
        return

    if not lista_palabras:
        await interaction.response.send_message("⚠️ El archivo `palabras.txt` está vacío o mal formateado.", ephemeral=True)
        return

    palabra_objetivo = obtener_palabra_del_dia()
    active_games[user_id] = {
        "palabra": palabra_objetivo,
        "intentos": 0,
        "historial": [],
        "canal_id": interaction.channel.id
    }

    await interaction.response.send_message(
        "🎮 ¡Partida iniciada! Usa `/intento palabra:<palabra>` para jugar.",
        ephemeral=True
    )
    

# slash historial

@bot.tree.command(name="historial", description="Muestra el historial de intentos de tu partida actual de Wordle")
async def historial_slash(interaction: discord.Interaction):
    limpiar_cache_si_cambio_dia()
    user_id = interaction.user.id

    if user_id not in active_games and user_id not in ended_games:
        await interaction.response.send_message("❌ Hoy no has jugado. Usa `/wordle` para empezar.", ephemeral=True)
        return

    if user_id in ended_games:
        partida = ended_games[user_id]
        is_completed = True
    else:
        partida = active_games[user_id]
        is_completed = False

    if not partida["historial"]:
        await interaction.response.send_message("⚠️ Aún no has hecho ningún intento.", ephemeral=True)
        return
    
    if is_completed:
        title = f"📋 Historial de Wordle — Completada en {partida['intentos']} intentos" if partida["intentos"] < 6 else "📋 Historial de Wordle — Fallida"
    else:
        title = f"📋 Historial de Wordle — Intento {partida['intentos']} de 6"

    embed = discord.Embed(
        title=title,
        color=discord.Color.teal()
    )

    grid = "\n".join(f"{l}\n{c}" for l, c in partida["historial"])
    embed.add_field(name="Progreso" if not is_completed else "Resultado", value=f"```{grid}```", inline=False)

    intentos_restantes = 6 - partida["intentos"]

    if is_completed:
        embed.add_field(name="Palabra del día", value=partida["palabra"].upper(), inline=False)
    else:
        if intentos_restantes > 0:
            embed.set_footer(text=f"{intentos_restantes} intento(s) restante(s)")
        else:
            embed.set_footer(text="Último intento")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    







def uwu(text):
    global def owo():
        return text.replace("r", "w").replace("l", "w").replace("R", "W").replace("L", "W")
    
owo()





bot.run("TOKEN")


