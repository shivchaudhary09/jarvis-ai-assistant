import json
import os

PREF_FILE = "preferences.json"

def load_preferences():
    if os.path.exists(PREF_FILE):
        try:
            with open(PREF_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_preference(new_pref):
    prefs = load_preferences()
    if new_pref not in prefs:
        prefs.append(new_pref)
    with open(PREF_FILE, "w") as f:
        json.dump(prefs, f, indent=2)

def replace_preferences(prefs_list):
    """Poori preference list overwrite kar do (conflict resolve hone ke baad)"""
    with open(PREF_FILE, "w") as f:
        json.dump(prefs_list, f, indent=2)

def preferences_as_text():
    prefs = load_preferences()
    if not prefs:
        return ""
    return "User ki known preferences:\n" + "\n".join(f"- {p}" for p in prefs)