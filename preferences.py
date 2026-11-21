import json
import os

PREF_FILE = "preferences.json"


def load_preferences():
    """Load user preferences from JSON storage."""
    if os.path.exists(PREF_FILE):
        try:
            with open(PREF_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def save_preference(new_pref):
    """Save a single new user preference."""
    prefs = load_preferences()
    if new_pref not in prefs:
        prefs.append(new_pref)
    with open(PREF_FILE, "w") as f:
        json.dump(prefs, f, indent=2)


def replace_preferences(prefs_list):
    """Overwrite the full preferences list (e.g. after resolving conflicts)."""
    with open(PREF_FILE, "w") as f:
        json.dump(prefs_list, f, indent=2)


def preferences_as_text():
    """Format stored user preferences as system prompt context."""
    prefs = load_preferences()
    if not prefs:
        return ""
    return "User's known preferences:\n" + "\n".join(f"- {p}" for p in prefs)
