import discord
from discord.ext import commands
import os
from discord import app_commands
import random
from discord.ui import View, button



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
    try:
        await bot.load_extension("cogs.reminders")
    except Exception as e:
        print("Error cargando reminders:", e)

    try:
        await bot.load_extension("cogs.birthdays")
    except Exception as e:
        print("Error cargando birthdays:", e)

    try:
        await bot.load_extension("cogs.join_left")
    except Exception as e:
        print("Error cargando join_left:", e)

    try:
        await bot.load_extension("cogs.reactions")
    except Exception as e:
        print("Error cargando reactions:", e)

    try:
        await bot.load_extension("cogs.wordle")
    except Exception as e:
        print("Error cargando wordle:", e)

    print(f"Connecting as {bot.user}...")

    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"Error sync commands: {e}")

    activity = discord.Activity(type=discord.ActivityType.watching, name="Juni")
    await bot.change_presence(status=discord.Status.online, activity=activity)

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
            
            
# slash carla
class carlaGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="carla", description="Opciones relacionadas con los comandos de carla.")

    @app_commands.command(name="imagen", description="Envía la ruleta de los estados de Carla.")
    async def ruleta(self, interaction: discord.Interaction):
        await interaction.response.defer()
        image_path = os.path.join("assets", "image2.png")
        with open(image_path, "rb") as f:
            file = discord.File(f, filename="image2.png")
            await interaction.followup.send(file=file)

    @app_commands.command(name="actual", description="Muestra un estado aleatorio de Carla.")
    async def actual(self, interaction: discord.Interaction):
        await interaction.response.defer()
        image_files = ["noche.PNG", "muejeje.PNG", "insane.gif", "breakdown.PNG"]
        selected_image = random.choice(image_files)
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
        embed.add_field(name="/juni", value="Menciona a Juni.", inline=False)
        embed.add_field(name="/help", value="Este menú de ayuda.", inline=False)
        embed.add_field(name="/cumpleaños ``[add/view/delete/edit]``", value="Gestiona los cumpleaños.", inline=False)
        embed.add_field(name="/recordatorio ``[add/view/delete]``", value="Gestiona recordatorios.", inline=False)
        embed.add_field(name="/estado imagen", value="Muestra los estados de Juni.", inline=False)
        embed.add_field(name="/estado actual", value="Muestra un estado aleatorio de Juni.", inline=False)
        embed.add_field(name="/carla imagen", value="Muestra los estados de Carla.", inline=False)
        embed.add_field(name="/carla actual", value="Muestra un estado aleatorio de Carla.", inline=False)
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

# slash crucigrama (Discord Activity)

CRUCIGRAMA_APP_ID = 449903611128971275

@bot.tree.command(name="crucigrama", description="Abre el crucigrama como actividad de Discord")
async def crucigrama_slash(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ Solo disponible en servidores.", ephemeral=True
        )
        return

    try:
        # Lanzar la actividad embebida en el canal de voz del usuario
        activity_url = f"https://discord.com/activities/{CRUCIGRAMA_APP_ID}"
        embed = discord.Embed(
            title="🧩 Crucigrama",
            description="¡Haz clic en el botón para jugar al crucigrama!",
            color=discord.Color.blue(),
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Jugar Crucigrama",
                url=activity_url,
                style=discord.ButtonStyle.link,
            )
        )
        await interaction.response.send_message(embed=embed, view=view)
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error al lanzar la actividad: {e}", ephemeral=True
        )




bot.run("your_token_here")


