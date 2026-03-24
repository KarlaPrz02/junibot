"""Register a Discord Activity Entry Point Command. Run once."""
import json
import urllib.request
import urllib.error

with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

TOKEN = cfg["bot"]["token"]
APP_ID = str(cfg["crucigrama"]["app_id"])

payload = json.dumps({
    "name": "launch",
    "type": 4,                # PRIMARY_ENTRY_POINT
    "description": "Lanza la actividad de juegos",
    "handler": 2              # DISCORD_LAUNCH_ACTIVITY
}).encode("utf-8")

url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"

req = urllib.request.Request(
    url,
    data=payload,
    headers={
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(f"Entry Point Command registered: name={data['name']}, id={data['id']}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"HTTP {e.code}: {body}")
