import asyncio
import json
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

REMINDERS_FILE = "reminders.json"
TZ = ZoneInfo("Europe/Madrid")
DATE_FORMAT = "%d-%m-%Y %H:%M"  

def _load_reminders():
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_reminders(data):
    tmp = REMINDERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REMINDERS_FILE)

def parse_datetime(text: str):
    """
    Intenta parsear la fecha en DATE_FORMAT y devuelve datetime con TZ.
    Lanza ValueError si no se puede parsear.
    """
    dt = datetime.fromisoformat(text) if "T" in text else None
    if dt is None:
        dt = datetime.strptime(text, DATE_FORMAT)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    else:
        dt = dt.astimezone(TZ)
    return dt

class Reminders(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = None
        self._lock = asyncio.Lock()
        self.reminders = _load_reminders()

    async def cog_load(self):
        # start background task
        self._task = asyncio.create_task(self._reminder_loop())

    async def cog_unload(self):
        # cancel background task on unload
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _reminder_loop(self):
        try:
            while True:
                now = datetime.now(TZ)
                to_send = []
                async with self._lock:
                    remaining = []
                    for r in self.reminders:
                        due = datetime.fromisoformat(r["time"])
                        if due.tzinfo is None:
                            due = due.replace(tzinfo=TZ)
                        if due <= now:
                            to_send.append(r)
                        else:
                            remaining.append(r)
                    if to_send:
                        # remove the ones to send
                        self.reminders = remaining
                        _save_reminders(self.reminders)
                # send outside lock
                for r in to_send:
                    try:
                        channel = self.bot.get_channel(r.get("channel_id")) if r.get("channel_id") is not None else None
                        user = await self.bot.fetch_user(r["user_id"])
                        mention = f"<@{r['user_id']}>"
                        text = r["message"]
                        if channel:
                            await channel.send(f"⏰ {mention} — Recordatorio: {text}")
                        else:
                            # try DM
                            if user:
                                await user.send(f"⏰ Recordatorio: {text}")
                    except Exception:
                        pass
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

    async def add_reminder(self, user_id: int, channel_id: Optional[int], time_dt: datetime, message: str, guild_id: Optional[int] = None):
        r = {
            "id": str(uuid.uuid4())[:8],
            "user_id": user_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "time": time_dt.isoformat(),
            "message": message,
            "created_at": datetime.now(TZ).isoformat()
        }
        async with self._lock:
            self.reminders.append(r)
            # mantener orden por tiempo
            self.reminders.sort(key=lambda x: x["time"])
            _save_reminders(self.reminders)
        return r

    async def list_user(self, user_id: int):
        async with self._lock:
            return [r for r in self.reminders if r["user_id"] == user_id]

    async def remove_by_id(self, user_id: int, rid: str):
        async with self._lock:
            before = len(self.reminders)
            self.reminders = [r for r in self.reminders if not (r["id"] == rid and r["user_id"] == user_id)]
            if len(self.reminders) < before:
                _save_reminders(self.reminders)
                return True
            return False

# /recordatorio command

ACTIONS = [
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="view", value="view"),
    app_commands.Choice(name="delete", value="delete"),
]

@app_commands.command(name="recordatorio", description="Gestiona recordatorios: add/view/delete")
@app_commands.choices(action=ACTIONS)
@app_commands.describe(
    action="Acción a realizar",
    fecha="Fecha y hora (DD-MM-YYYY HH:MM) — para add",
    texto="Texto del recordatorio — para add",
    id="ID del recordatorio — para delete"
)
async def recordatorio_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    fecha: Optional[str] = None,
    texto: Optional[str] = None,
    id: Optional[str] = None,
):
    await interaction.response.defer(ephemeral=True)
    cog: Reminders = interaction.client.get_cog("Reminders")
    if cog is None:
        await interaction.followup.send("Error interno: Ni puta idea de que ha pasado socio.", ephemeral=True)
        return

    act = action.value

    # ADD
    if act == "add":
        if not fecha or not texto:
            await interaction.followup.send("Debes indicar `fecha` (DD-MM-YYYY HH:MM) y `texto` para crear un recordatorio.", ephemeral=True)
            return
        try:
            dt = parse_datetime(fecha)
        except Exception:
            await interaction.followup.send("Formato de fecha inválido. Usa `DD-MM-YYYY HH:MM` (ej: 11-12-2025 14:30).", ephemeral=True)
            return
        now = datetime.now(TZ)
        if dt <= now:
            await interaction.followup.send("La fecha debe ser en el futuro.", ephemeral=True)
            return
        guild_id = getattr(interaction.guild, "id", None)
        channel_id = interaction.channel.id if interaction.channel else None
        r = await cog.add_reminder(interaction.user.id, channel_id, dt, texto, guild_id)
        await interaction.followup.send(f"Recordatorio creado (id: `{r['id']}`) para {dt.strftime(DATE_FORMAT)}.", ephemeral=True)
        return

    # VIEW
    if act == "view":
        items = await cog.list_user(interaction.user.id)
        if not items:
            await interaction.followup.send("No tienes recordatorios pendientes.", ephemeral=True)
            return
        lines = []
        for r in items:
            dt = datetime.fromisoformat(r["time"]).astimezone(TZ)
            ch = f"<#{r['channel_id']}>" if r.get("channel_id") else "DM"
            lines.append(f"`{r['id']}` — {dt.strftime(DATE_FORMAT)} — {ch} — {r['message']}")
        text = "\n".join(lines)
        await interaction.followup.send(f"Tus recordatorios:\n{text}", ephemeral=True)
        return

    # DELETE
    if act == "delete":
        if not id:
            await interaction.followup.send("Debes indicar el `id` del recordatorio a borrar (ver /recordatorio view).", ephemeral=True)
            return
        ok = await cog.remove_by_id(interaction.user.id, id)
        if ok:
            await interaction.followup.send(f"Recordatorio `{id}` eliminado.", ephemeral=True)
        else:
            await interaction.followup.send(f"No se encontró el recordatorio `{id}` (o no eres el propietario).", ephemeral=True)
        return

    await interaction.followup.send("Acción no reconocida.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Reminders(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(recordatorio_command)