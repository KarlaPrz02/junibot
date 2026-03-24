import httpx


class APIClient:
    def __init__(self, config=None):
        config = config or {}
        self.enabled = config.get("enabled", False)
        self.base_url = config.get("base_url", "http://127.0.0.1:8000").rstrip("/")
        self.timeout = float(config.get("timeout", 5))
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def create_log(self, message, level="info", source="juni-bot", tag=None):
        if not self.enabled:
            return None

        payload = {
            "message": message,
            "level": level,
            "source": source,
            "tag": tag,
        }

        try:
            response = await self.client.post(f"{self.base_url}/logs", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error enviando log: {e}", flush=True)
            return None

    async def get_stats(self):
        if not self.enabled:
            return None

        try:
            response = await self.client.get(f"{self.base_url}/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error leyendo stats: {e}", flush=True)
            return None

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
        
    async def create_reminder(self, reminder_id, user_id, channel_id, guild_id, remind_at, message, repeat_type="once", interval_days=1):
        if not self.enabled:
            return None

        payload = {
            "id": reminder_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "remind_at": remind_at,
            "message": message,
            "repeat_type": repeat_type,
            "interval_days": interval_days,
        }

        try:
            response = await self.client.post(f"{self.base_url}/reminders", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error creando reminder: {e}", flush=True)
            return None

    async def get_reminders(self, user_id=None, limit=50):
        if not self.enabled:
            return None

        params = {"limit": limit}
        if user_id is not None:
            params["user_id"] = user_id

        try:
            response = await self.client.get(f"{self.base_url}/reminders", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error leyendo reminders: {e}", flush=True)
            return None

    async def get_pending_reminders(self, limit=100):
        if not self.enabled:
            return None

        try:
            response = await self.client.get(f"{self.base_url}/reminders/pending", params={"limit": limit})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error leyendo reminders pendientes: {e}", flush=True)
            return None

    async def update_reminder(self, reminder_id, **fields):
        if not self.enabled:
            return None

        try:
            response = await self.client.patch(f"{self.base_url}/reminders/{reminder_id}", json=fields)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error actualizando reminder: {e}", flush=True)
            return None

    async def delete_reminder(self, reminder_id):
        if not self.enabled:
            return None

        try:
            response = await self.client.delete(f"{self.base_url}/reminders/{reminder_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error borrando reminder: {e}", flush=True)
            return None
        
    async def create_or_update_birthday(self, guild_id, user_id, date_str):
        if not self.enabled:
            return None

        payload = {
            "guild_id": guild_id,
            "user_id": user_id,
            "date": date_str,
        }

        try:
            response = await self.client.post(f"{self.base_url}/birthdays", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error creando/actualizando cumpleaños: {e}", flush=True)
            return None

    async def get_birthdays(self, guild_id=None, user_id=None, limit=500):
        if not self.enabled:
            return None

        params = {"limit": limit}
        if guild_id is not None:
            params["guild_id"] = guild_id
        if user_id is not None:
            params["user_id"] = user_id

        try:
            response = await self.client.get(f"{self.base_url}/birthdays", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error leyendo cumpleaños: {e}", flush=True)
            return None

    async def delete_birthday(self, guild_id, user_id):
        if not self.enabled:
            return None

        try:
            response = await self.client.delete(f"{self.base_url}/birthdays/{guild_id}/{user_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error borrando cumpleaños: {e}", flush=True)
            return None

    async def get_due_birthdays(self, today_iso, day_month, limit=500):
        if not self.enabled:
            return None

        params = {
            "today_iso": today_iso,
            "day_month": day_month,
            "limit": limit,
        }

        try:
            response = await self.client.get(f"{self.base_url}/birthdays/due", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error leyendo cumpleaños próximos: {e}", flush=True)
            return None

    async def update_birthday_state(self, guild_id, last_sent):
        if not self.enabled:
            return None

        payload = {"last_sent": last_sent}

        try:
            response = await self.client.patch(f"{self.base_url}/birthday-state/{guild_id}", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error actualizando estado de cumpleaños: {e}", flush=True)
            return None