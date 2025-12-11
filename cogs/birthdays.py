import asyncio
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

TZ = ZoneInfo("Europe/Madrid")
DATE_FORMAT = "%d-%m" 

DATA_FILE = "birthdays.json"  # guarda cumpleaños por servidor
CONFIG_FILE = "config.json"   # mapa guild_id -> channel_id 

def _load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_data(d):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

def _load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_config(d):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)

class Birthdays(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = None
        self._lock = asyncio.Lock()
        self.data = _load_data()    # birthdays and last_sent per guild
        self.config = _load_config()  # config: guild_id -> channel_id

    async def cog_load(self):
        self._task = asyncio.create_task(self._loop())

    async def cog_unload(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        try:
            while True:
                now = datetime.now(TZ).date()
                send_ops = []
                async with self._lock:
                    for guild_id, gdata in list(self.data.items()):
                        # prefer channel from config.json, fallback to gdata["channel_id"]
                        cfg_channel = self.config.get(str(guild_id))
                        channel_id = cfg_channel or gdata.get("channel_id")
                        if not channel_id:
                            continue
                        last_sent = gdata.get("last_sent")
                        # evitar duplicados 
                        if last_sent == now.isoformat():
                            continue
                        birthdays = gdata.get("birthdays", [])
                        matches = []
                        for b in birthdays:
                            try:
                                dt = datetime.strptime(b["date"], DATE_FORMAT).date()
                            except Exception:
                                continue
                            if dt.month == now.month and dt.day == now.day:
                                matches.append(b)
                        if matches:
                            send_ops.append((int(guild_id), int(channel_id), matches))
                            gdata["last_sent"] = now.isoformat()
                    if send_ops:
                        _save_data(self.data)
                # send messages out of lock
                for guild_id, channel_id, matches in send_ops:
                    try:
                        channel = self.bot.get_channel(channel_id)
                        mentions = " ".join(f"<@{m['user_id']}>" for m in matches)
                        names = ", ".join(f"<@{m['user_id']}>" for m in matches)
                        text = f"🎉 ¡Hoy es el cum-ple de {names}! 🎂\n{mentions}\n"
                        if channel:
                            await channel.send(f"@everyone\n{text}")
                    except Exception:
                        pass
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

    # helpers 
    async def add_birthday(self, guild_id: int, user_id: int, date_str: str):
        async with self._lock:
            gid = str(guild_id)
            if gid not in self.data:
                self.data[gid] = {"channel_id": None, "birthdays": [], "last_sent": None}
            b_list = self.data[gid].setdefault("birthdays", [])
            for b in b_list:
                if b["user_id"] == user_id:
                    b["date"] = date_str
                    _save_data(self.data)
                    return b
            newb = {"user_id": user_id, "date": date_str}
            b_list.append(newb)
            _save_data(self.data)
            return newb

    async def list_user(self, guild_id: int, user_id: int):
        async with self._lock:
            gid = str(guild_id)
            if gid not in self.data:
                return []
            return [b for b in self.data[gid].get("birthdays", []) if b["user_id"] == user_id]

    async def remove_birthday(self, guild_id: int, user_id: int):
        async with self._lock:
            gid = str(guild_id)
            if gid not in self.data:
                return False
            before = len(self.data[gid].get("birthdays", []))
            self.data[gid]["birthdays"] = [b for b in self.data[gid].get("birthdays", []) if b["user_id"] != user_id]
            if len(self.data[gid]["birthdays"]) < before:
                _save_data(self.data)
                return True
            return False

    async def set_channel(self, guild_id: int, channel_id: int):
        async with self._lock:
            gid = str(guild_id)
            if gid not in self.data:
                self.data[gid] = {"channel_id": channel_id, "birthdays": [], "last_sent": None}
            else:
                self.data[gid]["channel_id"] = channel_id
            _save_data(self.data)

ACTIONS = [
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="view", value="view"),
    app_commands.Choice(name="delete", value="delete"),
    app_commands.Choice(name="edit", value="edit"),
    app_commands.Choice(name="viewall", value="viewall"),
]

@app_commands.command(name="cumpleaños", description="Gestiona tu cumpleaños en este servidor: add/view/delete/edit")
@app_commands.choices(action=ACTIONS)
@app_commands.describe(action="Acción a realizar", fecha="Fecha (DD-MM) — para add", new_fecha="Nueva fecha (DD-MM) — para edit")
async def cumple_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    fecha: Optional[str] = None,
    new_fecha: Optional[str] = None,
):
    await interaction.response.defer(ephemeral=True)
    cog: Birthdays = interaction.client.get_cog("Birthdays")
    if cog is None:
        await interaction.followup.send("There was an error please try again later.", ephemeral=True)
        return

    act = action.value

    
    if interaction.guild is None:
        await interaction.followup.send("Este comando solo funciona en servidores.", ephemeral=True)
        return

    # ADD
    if act == "add":
        if not fecha:
            await interaction.followup.send("Debes indicar la fecha con formato `DD-MM`.", ephemeral=True)
            return
        try:
            dt = datetime.strptime(fecha, DATE_FORMAT).date()
        except Exception:
            await interaction.followup.send("Formato inválido. Usa `DD-MM` (ej: 11-12).", ephemeral=True)
            return
        await cog.add_birthday(interaction.guild.id, interaction.user.id, dt.strftime(DATE_FORMAT))
        await interaction.followup.send(f"✅ Tu cumpleaños ha sido guardado como `{dt.strftime(DATE_FORMAT)}` en este servidor.", ephemeral=True)
        return

    # VIEW
    if act == "view":
        items = await cog.list_user(interaction.guild.id, interaction.user.id)
        if not items:
            await interaction.followup.send("No tienes un cumpleaños guardado en este servidor.", ephemeral=True)
            return
        lines = [f"`{i['date']}`" for i in items]
        await interaction.followup.send("Tus cumpleaños guardados: " + ", ".join(lines), ephemeral=True)
        return

    # DELETE
    if act == "delete":
        ok = await cog.remove_birthday(interaction.guild.id, interaction.user.id)
        if ok:
            await interaction.followup.send("✅ Tu cumpleaños ha sido eliminado para este servidor.", ephemeral=True)
        else:
            await interaction.followup.send("No se encontró un cumpleaños tuyo en este servidor.", ephemeral=True)
        return

    # EDIT
    if act == "edit":
        if not new_fecha:
            await interaction.followup.send("Debes indicar la nueva fecha con `new_fecha` (`DD-MM`).", ephemeral=True)
            return
        try:
            ndt = datetime.strptime(new_fecha, DATE_FORMAT).date()
        except Exception:
            await interaction.followup.send("Formato inválido para `new_fecha`. Usa `DD-MM`.", ephemeral=True)
            return
        await cog.add_birthday(interaction.guild.id, interaction.user.id, ndt.strftime(DATE_FORMAT))
        await interaction.followup.send(f"✅ Tu cumpleaños ha sido actualizado a `{ndt.strftime(DATE_FORMAT)}` en este servidor.", ephemeral=True)
        return

    # VIEWALL (solo administradores)
    if act == "viewall":
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("Necesitas permisos de administrador para usar esta opción.", ephemeral=True)
            return

        gid = str(interaction.guild.id)
        # leer de forma segura
        async with cog._lock:
            guild_data = cog.data.get(gid, {})
            birthdays = guild_data.get("birthdays", [])

        if not birthdays:
            await interaction.followup.send("No hay cumpleaños registrados en este servidor.", ephemeral=True)
            return

        lines = []
        for b in birthdays:
            # fecha almacenada en formato DD-MM
            lines.append(f"<@{b['user_id']}> — `{b.get('date')}`")

        text = "\n".join(lines)
        await interaction.followup.send(f"Cumpleaños en este servidor:\n{text}", ephemeral=True)
        return

    await interaction.followup.send("Acción no reconocida.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Birthdays(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cumple_command)