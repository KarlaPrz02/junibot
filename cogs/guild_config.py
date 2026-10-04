import json
import os
from typing import Optional


CONFIG_FILE = "config.json"

CHANNEL_KEYS = {"birthdays", "member_join", "member_leave"}


def _load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def get_guild_channel_id(guild_id: int, key: str) -> Optional[int]:
    if key not in CHANNEL_KEYS:
        raise ValueError(f"Unknown guild channel setting: {key}")

    guild_config = _load_config().get("guilds", {}).get(str(guild_id), {})
    channels = guild_config.get("channels", {})
    if key in channels:
        channel_id = channels[key]
    else:
        legacy_key = "birthdays" if key == "birthdays" else "welcome"
        channel_id = guild_config.get(legacy_key)

    if channel_id is None or int(channel_id) <= 0:
        return None
    return int(channel_id)


def get_guild_role_id(guild_id: int, key: str) -> Optional[int]:
    if key != "member":
        raise ValueError(f"Unknown guild role setting: {key}")

    guild_config = _load_config().get("guilds", {}).get(str(guild_id), {})
    roles = guild_config.get("roles", {})
    if key in roles:
        role_id = roles[key]
    else:
        role_id = guild_config.get("member_role")

    if role_id is None or int(role_id) <= 0:
        return None
    return int(role_id)


def set_guild_setting(guild_id: int, category: str, key: str, value: Optional[int]) -> None:
    if category == "channels" and key not in CHANNEL_KEYS:
        raise ValueError(f"Unknown guild channel setting: {key}")
    if category == "roles" and key != "member":
        raise ValueError(f"Unknown guild role setting: {key}")
    if category not in {"channels", "roles"}:
        raise ValueError(f"Unknown guild setting category: {category}")

    config = _load_config()
    guilds = config.setdefault("guilds", {})
    guild_config = guilds.setdefault(str(guild_id), {})
    settings = guild_config.setdefault(category, {})
    settings[key] = value

    temporary_file = CONFIG_FILE + ".tmp"
    with open(temporary_file, "w", encoding="utf-8") as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=2)
    os.replace(temporary_file, CONFIG_FILE)
