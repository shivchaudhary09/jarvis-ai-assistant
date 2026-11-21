import subprocess
import requests
import os
import re
import time
from dotenv import load_dotenv

load_dotenv()

_cached_location = None
_last_location_check = 0.0


def get_gps_coordinates():
    """Retrieve actual GPS coordinates from macOS CoreLocation."""
    try:
        result = subprocess.run(
            ["CoreLocationCLI", "--format", "%latitude,%longitude"],
            capture_output=True, text=True, timeout=20
        )
        output = result.stdout.strip()
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", output)
        if result.returncode == 0 and match:
            lat, lon = match.groups()
            return float(lat), float(lon)
        print("[Location: CoreLocationCLI returned no coordinates; falling back to IP/env.]")
    except (subprocess.TimeoutExpired, OSError) as error:
        print(f"[Location: GPS unavailable ({error}); falling back to IP/env.]")
    return None, None


def reverse_geocode(lat, lon):
    """Convert coordinates into a human-readable location (city, state, country)."""
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "JARVIS-Assistant"},
            timeout=5
        )
        data = response.json()
        address = data.get("address", {})
        city = address.get("city") or address.get("town") or address.get("village") or ""
        state = address.get("state", "")
        country = address.get("country", "")
        return f"{city}, {state}, {country}".strip(", ")
    except Exception:
        return None


def get_ip_location():
    """Fallback location from current public IP address (city-level)."""
    try:
        response = requests.get("https://ipapi.co/json/", timeout=5)
        response.raise_for_status()
        data = response.json()
        city = data.get("city", "")
        region = data.get("region", "")
        country = data.get("country_name", "")
        location = ", ".join(part for part in (city, region, country) if part)
        return location or None
    except (requests.RequestException, ValueError):
        return None


def get_current_location():
    """Return the current location, caching results for 60 seconds."""
    global _cached_location, _last_location_check

    refresh_seconds = int(os.getenv("LOCATION_REFRESH_SECONDS", "60"))
    now = time.monotonic()
    if _cached_location and now - _last_location_check < refresh_seconds:
        return _cached_location

    lat, lon = get_gps_coordinates()
    if lat and lon:
        location = reverse_geocode(lat, lon)
        if location:
            _cached_location = location
            _last_location_check = now
            return _cached_location

    _cached_location = get_ip_location() or os.getenv("USER_LOCATION", "Unknown")
    _last_location_check = now
    return _cached_location
