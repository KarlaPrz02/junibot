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