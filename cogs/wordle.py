import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Optional


STATS_FILE = "stats.json"
FECHA_INICIO = datetime(2025, 6, 6, tzinfo=ZoneInfo("Europe/Madrid")).date()


class JugarWordleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Jugar", style=discord.ButtonStyle.primary, custom_id="jugar_wordle")
    async def jugar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Wordle")
        if cog:
            await cog.iniciar_wordle(interaction)


class Wordle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, Dict] = {}
        self.ended_games: Dict[int, Dict] = {}
        self.palabras_diarias = []
        self.user_stats: Dict[int, Dict[str, int]] = {}
        self.ultima_fecha = datetime.now(ZoneInfo("Europe/Madrid")).date()

    async def cog_load(self):
        self.cargar_stats()
        self.cargar_palabras()

    def cargar_palabras(self):
        print("Cargando palabras...")
        try:
            with open("palabras.txt", encoding="utf-8") as f:
                self.palabras_diarias = [line.strip().lower() for line in f if len(line.strip()) == 5]
        except FileNotFoundError:
            print("❌ No se encontró 'palabras.txt'")
            self.palabras_diarias = []
        print(f"Palabras cargadas: {len(self.palabras_diarias)}")

    def cargar_stats(self):
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    contenido = f.read().strip()
                    data = json.loads(contenido) if contenido else {}
                    self.user_stats = {int(k): v for k, v in data.items()}
            except (json.JSONDecodeError, IOError):
                print("⚠️ El archivo stats.json está vacío o corrupto. Se reinician las estadísticas.")
                self.user_stats = {}
        else:
            self.user_stats = {}

    def guardar_stats(self):
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.user_stats, f, ensure_ascii=False, indent=4)

    def obtener_palabra_del_dia(self):
        hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
        dias_transcurridos = (hoy - FECHA_INICIO).days
        if dias_transcurridos < len(self.palabras_diarias):
            return self.palabras_diarias[dias_transcurridos]
        else:
            return self.palabras_diarias[dias_transcurridos % len(self.palabras_diarias)]

    def limpiar_cache_si_cambio_dia(self):
        hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
        if hoy != self.ultima_fecha:
            self.active_games.clear()
            self.ultima_fecha = hoy

    def feedback(self, palabra_objetivo, intento):
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

    def actualizar_stats(self, user_id: int, victoria: bool):
        hoy = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
        self.user_stats.setdefault(user_id, {"victorias": 0, "derrotas": 0, "ultima_partida": ""})
        if victoria:
            self.user_stats[user_id]["victorias"] += 1
        else:
            self.user_stats[user_id]["derrotas"] += 1
        self.user_stats[user_id]["ultima_partida"] = hoy
        self.guardar_stats()

    async def iniciar_wordle(self, interaction: discord.Interaction):
        self.limpiar_cache_si_cambio_dia()
        user_id = interaction.user.id
        hoy = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()

        stats = self.user_stats.get(user_id, {})
        ultima = stats.get("ultima_partida")

        if ultima == hoy:
            await interaction.response.send_message("🕒 Ya jugaste al Wordle hoy. Podrás jugar de nuevo mañana.", ephemeral=True)
            return

        if user_id in self.active_games:
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

        palabra_objetivo = self.obtener_palabra_del_dia()
        self.active_games[user_id] = {
            "palabra": palabra_objetivo,
            "intentos": 0,
            "historial": [],
            "canal_id": interaction.channel.id
        }

        await interaction.response.send_message(
            "🎮 ¡Partida iniciada! Usa `/intento palabra:<palabra>` para jugar.",
            ephemeral=True
        )

    async def verificar_palabra_rae(self, palabra: str) -> bool:
        """Verifica si una palabra existe en el diccionario de la RAE."""
        def _consultar():
            url = f"https://dle.rae.es/{palabra}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8")
                    if "Aviso: palabra no encontrada" in html:
                        return False
                    return "<article" in html
            except Exception:
                return False
        return await asyncio.to_thread(_consultar)

    @app_commands.command(name="wordle", description="Juega al Wordle o añade palabras")
    @app_commands.describe(
        accion="Qué quieres hacer",
        palabra="Palabra de 5 letras (solo para añadir)"
    )
    @app_commands.choices(accion=[
        app_commands.Choice(name="jugar", value="jugar"),
        app_commands.Choice(name="añadir", value="añadir"),
    ])
    async def wordle_slash(self, interaction: discord.Interaction, accion: str, palabra: Optional[str] = None):
        if accion == "jugar":
            await self.iniciar_wordle(interaction)
        elif accion == "añadir":
            if not palabra:
                await interaction.response.send_message("❌ Debes indicar una palabra para añadir. Ejemplo: `/wordle añadir palabra:gatos`", ephemeral=True)
                return

            palabra = palabra.lower().strip()

            if len(palabra) != 5 or not palabra.isalpha():
                await interaction.response.send_message("❌ La palabra debe tener exactamente 5 letras.", ephemeral=True)
                return

            if palabra in self.palabras_diarias:
                await interaction.response.send_message("⚠️ Esa palabra ya está en la lista.", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            es_real = await self.verificar_palabra_rae(palabra)
            if not es_real:
                await interaction.followup.send("❌ Esa palabra no se encontró en el diccionario de la RAE.", ephemeral=True)
                return

            with open("palabras.txt", "a", encoding="utf-8") as f:
                f.write(f"\n{palabra}")
            self.palabras_diarias.append(palabra)

            await interaction.followup.send(f"✅ La palabra **{palabra}** se ha añadido al Wordle.", ephemeral=True)

    @app_commands.command(name="intento", description="Envía un intento para el Wordle en curso")
    @app_commands.describe(palabra="Tu intento de 5 letras")
    async def intento_slash(self, interaction: discord.Interaction, palabra: str):
        self.limpiar_cache_si_cambio_dia()
        user_id = interaction.user.id
        palabra = palabra.lower().strip()

        if user_id not in self.active_games:
            await interaction.response.send_message("❌ No tienes una partida activa. Usa `/wordle` para empezar.", ephemeral=True)
            return

        if len(palabra) != 5 or not palabra.isalpha():
            await interaction.response.send_message("❌ La palabra debe tener exactamente 5 letras.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        es_real = await self.verificar_palabra_rae(palabra)
        if not es_real:
            await interaction.followup.send("❌ Esa palabra no existe en el diccionario de la RAE.", ephemeral=True)
            return

        partida = self.active_games[user_id]
        palabra_objetivo = partida["palabra"]
        partida["intentos"] += 1

        letras, colores = self.feedback(palabra_objetivo, palabra)
        partida["historial"].append((letras, colores))

        canal = self.bot.get_channel(partida["canal_id"])
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

        await interaction.followup.send(embed=embed, ephemeral=True)

        if palabra == palabra_objetivo:
            mensaje_publico = f"✅ **{nombre_usuario}** adivinó la palabra en {partida['intentos']} intento(s).\n"
            grid = "\n".join(r for _, r in partida["historial"])
            mensaje_publico += "\n" + f"```{grid}```" + "\n"
            self.actualizar_stats(user_id, victoria=True)
            await canal.send(mensaje_publico, view=JugarWordleView())
            self.ended_games[user_id] = partida
            del self.active_games[user_id]

        elif partida["intentos"] >= 6:
            mensaje_publico = f"❌ **{nombre_usuario}** no adivinó la palabra en 6 intentos.\n"
            grid = "\n".join(r for _, r in partida["historial"])
            mensaje_publico += "\n" + f"```{grid}```" + "\n"
            self.actualizar_stats(user_id, victoria=False)
            await canal.send(mensaje_publico, view=JugarWordleView())
            self.ended_games[user_id] = partida
            del self.active_games[user_id]

    @app_commands.command(name="stats", description="Muestra tus estadísticas de Wordle")
    async def stats_slash(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        stats = self.user_stats.get(user_id, {"victorias": 0, "derrotas": 0})

        embed = discord.Embed(
            title=f"Estadísticas de {interaction.user.display_name}",
            color=discord.Color.green()
        )
        embed.add_field(name="Victorias", value=str(stats["victorias"]), inline=True)
        embed.add_field(name="Derrotas", value=str(stats["derrotas"]), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="top", description="Muestra el ranking de jugadores de Wordle")
    async def top_slash(self, interaction: discord.Interaction):
        if not self.user_stats:
            await interaction.response.send_message("📊 No hay estadísticas registradas todavía.", ephemeral=True)
            return

        ranking = sorted(self.user_stats.items(), key=lambda item: (item[1]["victorias"], -item[1]["derrotas"]), reverse=True)

        embed = discord.Embed(
            title="🏆 Ranking de Wordle",
            description="Top 10 jugadores con más victorias",
            color=discord.Color.gold()
        )

        for i, (user_id, stats) in enumerate(ranking[:10]):
            user = await self.bot.fetch_user(int(user_id))
            nombre = user.display_name if user else f"Usuario {user_id}"
            embed.add_field(
                name=f"{i+1}. {nombre}",
                value=f"✅ Victorias: {stats['victorias']} | ❌ Derrotas: {stats['derrotas']}",
                inline=False
            )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Ver stats online", url="https://karlaprz02.github.io/wordle/"))

        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="historial", description="Muestra el historial de intentos de tu partida actual de Wordle")
    async def historial_slash(self, interaction: discord.Interaction):
        self.limpiar_cache_si_cambio_dia()
        user_id = interaction.user.id

        if user_id not in self.active_games and user_id not in self.ended_games:
            await interaction.response.send_message("❌ Hoy no has jugado. Usa `/wordle` para empezar.", ephemeral=True)
            return

        if user_id in self.ended_games:
            partida = self.ended_games[user_id]
            is_completed = True
        else:
            partida = self.active_games[user_id]
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Wordle(bot))
