import asyncio
import uuid
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

CONFIG_FILE = "config.json"


def _load_bot_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_CONFIG = _load_bot_config()
TZ = ZoneInfo(_CONFIG.get("timezone", "Europe/Madrid"))
DATE_FORMAT = "%d-%m-%Y %H:%M"
MAX_REMINDER_TEXT = 1500

WEEKDAY_MAP = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

TIME_PATTERNS = [
    re.compile(
        r"\ben\s+(?P<amount>\d+)\s*(?P<unit>min(?:uto)?s?|hora?s?|dia?s?|d[ií]a?s?|semana?s?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<day>pasado\s+mañana|pasado\s+manana|mañana|manana|hoy)\s*(?:a\s+las\s*|a\s*las\s*|a\s*)?(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:el\s+)?(?P<weekday>lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)\s*(?:a\s+las\s*|a\s*las\s*|a\s*)?(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<day>pasado\s+mañana|pasado\s+manana|mañana|manana|hoy)\b",
        re.IGNORECASE,
    ),
]

TRIGGER_PATTERNS = [
    re.compile(r"\brecu[eé]rdame\b", re.IGNORECASE),
    re.compile(r"\brecuerdame\b", re.IGNORECASE),
    re.compile(r"\bacu[eé]rdame\b", re.IGNORECASE),
    re.compile(r"\bacuerdame\b", re.IGNORECASE),
    re.compile(r"\bav[ií]same\b", re.IGNORECASE),
    re.compile(r"\bavisame\b", re.IGNORECASE),
]


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


def _normalize_spaces(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text.strip("-:,. ")


def _parse_time_bits(hour_text: str, minute_text: Optional[str]) -> tuple[int, int]:
    hour = int(hour_text)
    minute = int(minute_text or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Hora inválida")
    return hour, minute


def _build_relative_datetime(amount: int, unit: str, now: datetime) -> datetime:
    unit = unit.lower()
    if unit.startswith("min"):
        delta = timedelta(minutes=amount)
    elif unit.startswith("hora"):
        delta = timedelta(hours=amount)
    elif unit.startswith("semana"):
        delta = timedelta(weeks=amount)
    else:
        delta = timedelta(days=amount)
    return now + delta


def _build_named_day_datetime(day_text: str, hour: int, minute: int, now: datetime) -> datetime:
    lowered = day_text.lower().strip()
    if lowered in ("hoy",):
        days = 0
    elif lowered in ("mañana", "manana"):
        days = 1
    elif lowered in ("pasado mañana", "pasado manana"):
        days = 2
    else:
        raise ValueError("Día no soportado")

    target = (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        raise ValueError("La fecha debe ser en el futuro")
    return target


def _build_weekday_datetime(weekday_text: str, hour: int, minute: int, now: datetime) -> datetime:
    lowered = weekday_text.lower().strip()
    target_weekday = WEEKDAY_MAP[lowered]
    days_ahead = (target_weekday - now.weekday()) % 7
    target = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=7)
    return target


def extract_natural_datetime(text: str, now: Optional[datetime] = None) -> tuple[datetime, str]:
    """
    Devuelve (datetime, texto_sin_la_parte_temporal).
    Soporta expresiones como:
    - en 20 min
    - mañana a las 19:00
    - hoy a las 22
    - pasado mañana a las 9
    - viernes a las 18:30
    """
    now = now or datetime.now(TZ)
    source = _normalize_spaces(text)
    lowered = source.lower()

    # 1) Relativo: "en 20 min"
    match = TIME_PATTERNS[0].search(lowered)
    if match:
        amount = int(match.group("amount"))
        dt = _build_relative_datetime(amount, match.group("unit"), now)
        remaining = _normalize_spaces(source[: match.start()] + " " + source[match.end() :])
        return dt, remaining

    # 2) Hoy / mañana / pasado mañana con hora
    match = TIME_PATTERNS[1].search(lowered)
    if match:
        hour, minute = _parse_time_bits(match.group("hour"), match.group("minute"))
        dt = _build_named_day_datetime(match.group("day"), hour, minute, now)
        remaining = _normalize_spaces(source[: match.start()] + " " + source[match.end() :])
        return dt, remaining

    # 3) Día de la semana con hora
    match = TIME_PATTERNS[2].search(lowered)
    if match:
        hour, minute = _parse_time_bits(match.group("hour"), match.group("minute"))
        dt = _build_weekday_datetime(match.group("weekday"), hour, minute, now)
        remaining = _normalize_spaces(source[: match.start()] + " " + source[match.end() :])
        return dt, remaining

    # 4) Hoy / mañana / pasado mañana sin hora -> por defecto 09:00
    match = TIME_PATTERNS[3].search(lowered)
    if match:
        dt = _build_named_day_datetime(match.group("day"), 9, 0, now)
        remaining = _normalize_spaces(source[: match.start()] + " " + source[match.end() :])
        return dt, remaining

    raise ValueError(
        "No pude entender la fecha. Prueba con 'en 20 min', 'mañana a las 19:00' o 'viernes a las 18:00'."
    )


def strip_bot_mention(text: str, bot_user_id: Optional[int]) -> str:
    cleaned = text or ""
    if bot_user_id is not None:
        cleaned = cleaned.replace(f"<@{bot_user_id}>", " ")
        cleaned = cleaned.replace(f"<@!{bot_user_id}>", " ")
    return _normalize_spaces(cleaned)


def remove_trigger_phrase(text: str) -> tuple[str, bool]:
    for pattern in TRIGGER_PATTERNS:
        match = pattern.search(text)
        if match:
            cleaned = _normalize_spaces(text[: match.start()] + " " + text[match.end() :])
            return cleaned, True
    return _normalize_spaces(text), False


def clip_text(text: str, max_len: int = MAX_REMINDER_TEXT) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


async def resolve_referenced_message(message: discord.Message) -> Optional[discord.Message]:
    if not message.reference:
        return None

    if isinstance(message.reference.resolved, discord.Message):
        return message.reference.resolved

    if message.reference.message_id is None or message.channel is None:
        return None

    try:
        return await message.channel.fetch_message(message.reference.message_id)
    except Exception:
        return None


def build_reply_reminder_text(source_message: discord.Message, extra_text: str = "") -> str:
    author_name = getattr(source_message.author, "display_name", None) or str(source_message.author)
    content = (source_message.content or "[mensaje sin texto]").strip()
    content = clip_text(content, 800)

    parts = []
    if extra_text:
        parts.append(extra_text)
    parts.append(f"Mensaje respondido de {author_name}: {content}")
    parts.append(f"Enlace: {source_message.jump_url}")
    return clip_text("\n".join(parts))


class Reminders(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = None
        self._lock = asyncio.Lock()

    async def cog_load(self):
        self._task = asyncio.create_task(self._reminder_loop())

    async def cog_unload(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _send_due_reminder(self, reminder: dict):
        channel = None
        user = None

        channel_id = reminder.get("channel_id")
        if channel_id is not None:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    channel = None

        try:
            user = await self.bot.fetch_user(reminder["user_id"])
        except Exception:
            user = None

        mention = f"<@{reminder['user_id']}>"
        text = reminder["message"]

        if channel is not None:
            await channel.send(f"⏰ {mention} — Recordatorio: {text}")
        elif user is not None:
            await user.send(f"⏰ Recordatorio: {text}")
        else:
            raise RuntimeError("No pude encontrar ni el canal ni el usuario para enviar el recordatorio")

    async def _reminder_loop(self):
        try:
            while True:
                pendientes = await self.bot.api.get_pending_reminders(limit=100)

                if pendientes:
                    now = datetime.now(TZ)

                    for r in pendientes:
                        try:
                            due = datetime.fromisoformat(r["remind_at"])
                            if due.tzinfo is None:
                                due = due.replace(tzinfo=TZ)
                            else:
                                due = due.astimezone(TZ)

                            await self._send_due_reminder(r)

                            repeat = r.get("repeat_type", "once")
                            interval = int(r.get("interval_days", 1) or 1)

                            if repeat == "once":
                                await self.bot.api.delete_reminder(r["id"])
                            else:
                                if repeat == "daily":
                                    step = timedelta(days=1)
                                else:
                                    step = timedelta(days=interval)

                                next_due = due + step
                                while next_due <= now:
                                    next_due += step

                                await self.bot.api.update_reminder(
                                    r["id"],
                                    remind_at=next_due.isoformat(),
                                )

                        except Exception as e:
                            print(f"[REMINDERS] Error procesando reminder {r.get('id')}: {e}", flush=True)

                await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

    async def add_reminder(
        self,
        user_id: int,
        channel_id: Optional[int],
        time_dt: datetime,
        message: str,
        guild_id: Optional[int] = None,
        repeat_type: str = "once",
        interval_days: int = 1,
    ):
        reminder_id = str(uuid.uuid4())[:8]

        result = await self.bot.api.create_reminder(
            reminder_id=reminder_id,
            user_id=user_id,
            channel_id=channel_id,
            guild_id=guild_id,
            remind_at=time_dt.isoformat(),
            message=message,
            repeat_type=repeat_type,
            interval_days=interval_days,
        )
        return result

    async def list_user(self, user_id: int):
        items = await self.bot.api.get_reminders(user_id=user_id, limit=100)
        return items or []

    async def remove_by_id(self, user_id: int, rid: str):
        items = await self.bot.api.get_reminders(user_id=user_id, limit=200)
        if not items:
            return False

        target = next((r for r in items if r["id"] == rid and r["user_id"] == user_id), None)
        if not target:
            return False

        result = await self.bot.api.delete_reminder(rid)
        return bool(result)

    async def create_from_natural_message(self, message: discord.Message):
        content = strip_bot_mention(message.content, getattr(self.bot.user, "id", None))
        content, has_trigger = remove_trigger_phrase(content)

        if not has_trigger:
            return

        try:
            remind_at, remaining_text = extract_natural_datetime(content)
        except ValueError as e:
            await message.reply(
                "No entendí la fecha 😵\n"
                "Prueba algo como:\n"
                "- `@Junibot recuérdame estudiar en 2 horas`\n"
                "- `@Junibot avísame mañana a las 19:00`\n"
                "- `@Junibot recuérdame esto el viernes a las 18:00`\n"
                f"Detalle: {e}",
                mention_author=False,
            )
            return

        now = datetime.now(TZ)
        if remind_at <= now:
            await message.reply("La fecha debe estar en el futuro.", mention_author=False)
            return

        referenced = await resolve_referenced_message(message)
        if referenced is not None:
            reminder_text = build_reply_reminder_text(referenced, remaining_text)
        else:
            reminder_text = clip_text(remaining_text)

        if not reminder_text:
            await message.reply(
                "Me falta el texto del recordatorio. Ejemplo: `@Junibot recuérdame estudiar en 2 horas`.",
                mention_author=False,
            )
            return

        channel_id = message.channel.id if message.channel else None
        guild_id = getattr(message.guild, "id", None)

        result = await self.add_reminder(
            user_id=message.author.id,
            channel_id=channel_id,
            time_dt=remind_at,
            message=reminder_text,
            guild_id=guild_id,
            repeat_type="once",
            interval_days=1,
        )

        await message.reply(
            f"✅ Recordatorio creado (`{result['id']}`) para **{remind_at.strftime(DATE_FORMAT)}**.",
            mention_author=False,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user is None:
            return

        raw = message.content or ""
        mention_plain = f"<@{self.bot.user.id}>"
        mention_nick = f"<@!{self.bot.user.id}>"
        if mention_plain not in raw and mention_nick not in raw:
            return

        async with self._lock:
            try:
                await self.create_from_natural_message(message)
            except Exception as e:
                print(f"[REMINDERS] Error creando reminder por mensaje: {e}", flush=True)
                try:
                    await message.reply(
                        "Hubo un error al crear el recordatorio. Revisa el formato o prueba con `/recordatorio add`.",
                        mention_author=False,
                    )
                except Exception:
                    pass


# /recordatorio command
ACTIONS = [
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="view", value="view"),
    app_commands.Choice(name="delete", value="delete"),
]

REPEAT_CHOICES = [
    app_commands.Choice(name="once", value="once"),
    app_commands.Choice(name="daily", value="daily"),
    app_commands.Choice(name="custom", value="custom"),
]


class ReminderModal(discord.ui.Modal):
    def __init__(self, cog: Reminders, opener_id: int, channel_id: Optional[int]):
        super().__init__(title="Crear recordatorio")
        self.cog = cog
        self.opener_id = opener_id
        self.channel_id = channel_id
        self.add_item(
            discord.ui.TextInput(
                label="Fecha (DD-MM-YYYY HH:MM)",
                placeholder="11-12-2025 14:30",
                style=discord.TextStyle.short,
            )
        )
        self.add_item(discord.ui.TextInput(label="Texto del recordatorio", style=discord.TextStyle.paragraph))
        self.add_item(
            discord.ui.TextInput(
                label="Repetición (once/daily/custom)",
                placeholder="once",
                style=discord.TextStyle.short,
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Intervalo en días (para custom)",
                placeholder="1",
                style=discord.TextStyle.short,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.opener_id:
            await interaction.response.send_message(
                "Solo quien abrió el formulario puede enviarlo.", ephemeral=True
            )
            return

        vals = [c.value.strip() for c in self.children]
        fecha_text, texto_text, repeat_text, intervalo_text = vals[0], vals[1], vals[2].lower() or "once", vals[3] or "1"
        try:
            dt = parse_datetime(fecha_text)
        except Exception:
            await interaction.response.send_message(
                "Formato de fecha inválido. Usa `DD-MM-YYYY HH:MM`.", ephemeral=True
            )
            return

        now = datetime.now(TZ)
        if dt <= now:
            await interaction.response.send_message("La fecha debe ser en el futuro.", ephemeral=True)
            return
        if repeat_text not in ("once", "daily", "custom"):
            await interaction.response.send_message(
                "Repetición inválida. Usa once/daily/custom.", ephemeral=True
            )
            return
        try:
            interval = int(intervalo_text)
        except Exception:
            interval = 1
        if repeat_text == "custom" and interval < 1:
            await interaction.response.send_message(
                "Intervalo inválido. Debe ser >= 1.", ephemeral=True
            )
            return

        guild_id = getattr(interaction.guild, "id", None)
        r = await self.cog.add_reminder(
            interaction.user.id,
            self.channel_id,
            dt,
            texto_text,
            guild_id,
            repeat_type=repeat_text,
            interval_days=interval,
        )

        await interaction.response.send_message(
            f"Recordatorio creado (id: `{r['id']}`) para {dt.strftime(DATE_FORMAT)}. Repetición: {repeat_text}",
            ephemeral=True,
        )


class ReminderButtonView(discord.ui.View):
    def __init__(self, cog: Reminders, opener_id: int, timeout: Optional[float] = 180.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.opener_id = opener_id

    @discord.ui.button(label="Abrir formulario", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opener_id:
            await interaction.response.send_message(
                "Solo quien inició puede usar este botón.", ephemeral=True
            )
            return
        ch_id = interaction.channel.id if interaction.channel else None
        modal = ReminderModal(self.cog, self.opener_id, ch_id)
        await interaction.response.send_modal(modal)


@app_commands.command(name="recordatorio", description="Gestiona recordatorios: add/view/delete")
@app_commands.choices(action=ACTIONS, repeat=REPEAT_CHOICES)
@app_commands.describe(
    action="Acción a realizar",
    fecha="Fecha y hora (DD-MM-YYYY HH:MM) — para add",
    texto="Texto del recordatorio — para add",
    id="ID del recordatorio — para delete",
    repeat="Tipo de repetición: once/daily/custom — para add",
    intervalo="Intervalo en días para custom — para add",
)
async def recordatorio_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    fecha: Optional[str] = None,
    texto: Optional[str] = None,
    id: Optional[str] = None,
    repeat: Optional[app_commands.Choice[str]] = None,
    intervalo: Optional[int] = None,
):
    await interaction.response.defer(ephemeral=True)
    cog: Reminders = interaction.client.get_cog("Reminders")
    if cog is None:
        await interaction.followup.send("Error interno: Ni puta idea de que ha pasado socio.", ephemeral=True)
        return

    act = action.value

    if act == "add":
        if not fecha or not texto:
            view = ReminderButtonView(cog, interaction.user.id)
            await interaction.followup.send(
                "Pulsa el botón para abrir el formulario de creación de recordatorio:",
                view=view,
                ephemeral=True,
            )
            return
        try:
            dt = parse_datetime(fecha)
        except Exception:
            await interaction.followup.send(
                "Formato de fecha inválido. Usa `DD-MM-YYYY HH:MM` (ej: 11-12-2025 14:30).",
                ephemeral=True,
            )
            return
        now = datetime.now(TZ)
        if dt <= now:
            await interaction.followup.send("La fecha debe ser en el futuro.", ephemeral=True)
            return
        rtype = repeat.value if repeat else "once"
        interval = int(intervalo) if intervalo is not None else 1
        if rtype not in ("once", "daily", "custom"):
            await interaction.followup.send(
                "Tipo de repetición inválido. Usa once/daily/custom.", ephemeral=True
            )
            return
        if rtype == "custom" and interval < 1:
            await interaction.followup.send(
                "Intervalo inválido. Debe ser un número entero de días >= 1.", ephemeral=True
            )
            return
        guild_id = getattr(interaction.guild, "id", None)
        channel_id = interaction.channel.id if interaction.channel else None
        r = await cog.add_reminder(
            interaction.user.id,
            channel_id,
            dt,
            texto,
            guild_id,
            repeat_type=rtype,
            interval_days=interval,
        )
        await interaction.followup.send(
            f"Recordatorio creado (id: `{r['id']}`) para {dt.strftime(DATE_FORMAT)}. "
            f"Repetición: {rtype}{(' cada ' + str(interval) + ' días') if rtype == 'custom' else ''}",
            ephemeral=True,
        )
        return

    if act == "view":
        items = await cog.list_user(interaction.user.id)
        if not items:
            await interaction.followup.send("No tienes recordatorios pendientes.", ephemeral=True)
            return
        lines = []
        for r in items:
            dt = datetime.fromisoformat(r["remind_at"]).astimezone(TZ)
            ch = f"<#{r['channel_id']}>" if r.get("channel_id") else "DM"
            rtype = r.get("repeat_type", "once")
            interval = int(r.get("interval_days", 1) or 1)
            rep_text = rtype if rtype != "custom" else f"custom every {interval}d"
            lines.append(f"`{r['id']}` — {dt.strftime(DATE_FORMAT)} — {ch} — {r['message']} — {rep_text}")
        text = "\n".join(lines)
        await interaction.followup.send(f"Tus recordatorios:\n{text}", ephemeral=True)
        return

    if act == "delete":
        if not id:
            await interaction.followup.send(
                "Debes indicar el `id` del recordatorio a borrar (ver /recordatorio view).",
                ephemeral=True,
            )
            return
        ok = await cog.remove_by_id(interaction.user.id, id)
        if ok:
            await interaction.followup.send(f"Recordatorio `{id}` eliminado.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"No se encontró el recordatorio `{id}` (o no eres el propietario).",
                ephemeral=True,
            )
        return

    await interaction.followup.send("Acción no reconocida.", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = Reminders(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(recordatorio_command)
