from os import path
from json import load
import typing
import re

SOCIAL_MAPS = {
    "facebook": {
        "login": "https://m.facebook.com/login",
        "filename": "facebook-cookies.json",
    }
}

PROJECT_ROOT = path.dirname(path.abspath(__name__))

# =============== CONFIGURE THIS ===============
DELAY_MIN = 20
DELAY_MAX = 30
SHUFFLE_GROUPS = True
TYPING_DELAY = 100
MAX_RETRIES = 3
LOOP_DELAY_MIN = 20 * 60
LOOP_DELAY_MAX = 30 * 60
DISCORD_WEBHOOK_URL = ""
# ==============================================

def get_sources_list() -> typing.List:
    with open(f"{PROJECT_ROOT}/groups.json", "r", encoding="utf-8") as sources_file:
        raw = load(sources_file)
    
    groups = []
    for item in raw:
        if isinstance(item, str):
            item_str = item.strip()
            if "facebook.com/groups/" in item_str:
                match = re.search(r"facebook\.com/groups/([^/?]+)", item_str)
                username = match.group(1) if match else item_str.strip("/")
            else:
                username = item_str
            groups.append({"username": username, "name": ""})
        elif isinstance(item, dict):
            groups.append({"username": item["username"], "name": item.get("name", "")})
    
    return groups
