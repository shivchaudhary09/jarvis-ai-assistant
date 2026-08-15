import atexit
import os
import json
import re
import time
from dotenv import load_dotenv
from ai_router import AIRouter
from automation import create_folder, create_file, rename_item, delete_item, open_app, list_files
from voice import listen, speak
from wake_word import listen_for_wake_word
from orb import OrbController
from preferences import load_preferences, save_preference, preferences_as_text, replace_preferences
from location import get_current_location

load_dotenv()

MEMORY_FILE = "memory.json"

BASE_PROMPT = """
Tum JARVIS ho — Shiv Chaudhary ke personal AI assistant, unhi ke dwara banaye gaye.
LIVE LOCATION (authoritative; GPS/IP fallback): {current_location}

Tumhari personality:
- Polite lekin thoda witty aur sarcastic, jaise Tony Stark ka JARVIS
- Shiv ko "Sir" bol sakte ho occasionally, lekin zyada formal mat bano
- Hinglish mein baat karo agar Shiv Hinglish mein baat kare, English mein karo agar wo English use kare
- Jawab short aur to-the-point do, lambi lecture mat do jab tak specifically na maanga jaye
- Thoda humor use karo jaha appropriate ho
- Shiv ke kaam (IT support, Python automation, DSA learning) ke context mein helpful raho
- Location ke baare mein purani chat history ki koi bhi baat ignore karo; LIVE LOCATION line authoritative hai.
"""


def load_history():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def save_history(history):
    with open(MEMORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def build_system_prompt():
    current_location = get_current_location()
    return BASE_PROMPT.format(current_location=current_location) + "\n\n" + preferences_as_text()


def wants_text_mode(user_input):
    text_mode_phrases = (
        "switch to text mode", "text mode", "text mein", "text mai",
        "typing mode", "type mode", "keyboard mode",
        "voice mode off", "voice off", "voice band", "bolna band",
    )
    normalised_input = user_input.lower().strip()
    return any(phrase in normalised_input for phrase in text_mode_phrases)


def wants_voice_session_exit(user_input):
    normalised_input = user_input.lower().strip()
    exit_phrases = (
        "band ho ja", "band ho", "band kar do", "bas karo", "chup ho ja",
        "get lost", "go away", "aaj ke liye bas", "aaj ke liye baas",
        "that's all", "thats all", "stop listening",
        "goodbye jarvis", "bye jarvis", "bye", "goodbye", "ok bye", "theek hai bye",
    )
    return any(phrase in normalised_input for phrase in exit_phrases)


def resolve_automation_path(path, default_to_desktop=False):
    if not path:
        return None

    path = os.path.expanduser(str(path).strip())
    if path.lower().startswith("/desktop/"):
        path = os.path.join(os.path.expanduser("~"), path.lstrip("/"))
    if os.path.isabs(path):
        return os.path.normpath(path)

    home = os.path.expanduser("~")
    special_directories = {
        "desktop": "Desktop", "downloads": "Downloads", "documents": "Documents",
        "pictures": "Pictures", "music": "Music", "movies": "Movies",
    }
    path_parts = path.replace("\\", "/").split("/", 1)
    special_name = special_directories.get(path_parts[0].lower())
    if special_name:
        suffix = path_parts[1] if len(path_parts) > 1 else ""
        return os.path.join(home, special_name, suffix) if suffix else os.path.join(home, special_name)
    if default_to_desktop:
        return os.path.join(home, "Desktop", path)
    return os.path.abspath(path)


def item_name_from_request(user_input):
    match = re.search(r"(?:naam|name|named|called)\s+([A-Za-z0-9][A-Za-z0-9_. -]*)", user_input, re.IGNORECASE)
    if not match:
        return None
    name = match.group(1).strip().rstrip(".!?,")
    return re.sub(
        r"\s+(?:on|in|at|from)\s+(?:my|the)?\s*(?:desktop|downloads|documents|pictures|music|movies)$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()


def requested_directory(user_input):
    match = re.search(r"\b(desktop|downloads|documents|pictures|music|movies)\b", user_input, re.IGNORECASE)
    return match.group(1) if match else None


def local_automation_action(user_input):
    lowered = user_input.lower().strip()
    item_name = item_name_from_request(user_input)
    destination = requested_directory(user_input)

    if (
        "folder" in lowered
        and any(word in lowered for word in ("bana", "bna", "create", "make", "new"))
        and item_name
    ):
        return {"action": "create_folder", "path": os.path.join(destination, item_name) if destination else item_name}

    if "file" in lowered and any(word in lowered for word in ("bana", "bna", "create", "make", "new")):
        match = re.search(r"(?:naam|name|named|called)\s+([A-Za-z0-9][A-Za-z0-9_. -]*)", user_input, re.IGNORECASE)
        if match:
            filename = match.group(1).strip().rstrip(".!?,")
            parent_match = re.search(r"([A-Za-z0-9_. -]+)\s+folder", user_input, re.IGNORECASE)
            if parent_match:
                filename = os.path.join(parent_match.group(1).strip(), filename)
            return {"action": "create_file", "path": filename, "content": ""}

    if "desktop" in lowered and any(word in lowered for word in ("files", "file", "list", "dikha", "bata")):
        return {"action": "list_files", "path": "Desktop"}

    if has_delete_intent(user_input):
        path_match = re.search(r"(?:~|/Users/)[^\s,]+", user_input)
        if path_match:
            return {"action": "delete", "path": path_match.group(0).rstrip(".!?,")}

        before_delete = re.search(
            r"(?:desktop\s+(?:par|pe|se)\s+)?(?:folder|file)?\s*([A-Za-z0-9][A-Za-z0-9_. -]*?)\s+(?:delete|remove|hata)",
            user_input,
            re.IGNORECASE,
        )
        after_delete = re.search(
            r"(?:delete|remove|hata)(?:\s+(?:folder|file|this|the))*\s+([A-Za-z0-9][A-Za-z0-9_. -]*)",
            user_input,
            re.IGNORECASE,
        )
        target_match = before_delete or after_delete
        if target_match:
            target = target_match.group(1).strip().rstrip(".!?,")
            target = re.sub(
                r"\s+(?:from|on|in)\s+(?:(?:my|the)\s+)?(?:desktop|downloads|documents|pictures|music|movies)$",
                "",
                target,
                flags=re.IGNORECASE,
            ).strip()
            target = re.sub(
                r"\s+(?:desktop|downloads|documents|pictures|music|movies)\s+(?:se|par|pe)$",
                "",
                target,
                flags=re.IGNORECASE,
            ).strip()
            target = re.sub(r"\s+(?:folder|file)(?:\s+ko)?$", "", target, flags=re.IGNORECASE).strip()
            target = re.sub(r"\s+ko$", "", target, flags=re.IGNORECASE).strip()
            if destination:
                target = os.path.join(destination, target)
            return {"action": "delete", "path": target}

        return {"action": "delete", "path": None}

    known_apps = {
        "calculator": "Calculator", "safari": "Safari", "finder": "Finder",
        "notes": "Notes", "terminal": "Terminal", "textedit": "TextEdit",
        "chrome": "Google Chrome", "google chrome": "Google Chrome",
        "vs code": "Visual Studio Code", "visual studio code": "Visual Studio Code",
        "spotify": "Spotify", "slack": "Slack", "discord": "Discord",
    }
    if any(word in lowered for word in ("khol", "open", "launch")):
        for name, app_name in known_apps.items():
            if name in lowered:
                return {"action": "open_app", "app_name": app_name}

        app_match = re.search(r"^(.+?)\s+khol(?:\s+(?:do|de|kar))?", user_input, re.IGNORECASE)
        if not app_match:
            app_match = re.search(r"(?:open|launch)\s+(.+?)(?:\s+(?:open|karo|kar|please))?$", user_input, re.IGNORECASE)
        if app_match:
            app_name = app_match.group(1).strip(" .,!?")
            if app_name:
                return {"action": "open_app", "app_name": app_name}

    return None


def has_delete_intent(user_input):
    lowered = user_input.lower().strip()
    delete_phrases = (
        "delete kar", "delete karo", "delete this", "delete the", "remove this",
        "remove the", "hata do", "hata de", "folder delete", "file delete",
        "delete folder", "delete file", "remove folder", "remove file",
    )
    if any(phrase in lowered for phrase in delete_phrases):
        return True
    if lowered.startswith(("kyu ", "kyon ", "why ", "what ", "how ", "kaise ")):
        return False
    return bool(re.search(r"\b(?:delete|remove)\s+[a-z0-9_./~-]+", lowered))


def detect_and_run_automation(user_input):
    automation_keywords = (
        "folder bana", "folder bna", "folder create", "create folder", "create a folder",
        "make folder", "make a folder", "new folder", "folder name",
        "file bana", "file bna", "file create", "create file", "create a file", "rename kar", "rename",
        "khol", "open kar", "open ", "launch ",
        "files dikha", "files bata", "list kar", "list files",
    )
    if not any(keyword in user_input.lower() for keyword in automation_keywords) and not has_delete_intent(user_input):
        return None

    extraction_prompt = f'''You are JARVIS's automation command parser.
User message: "{user_input}"

Convert it to exactly one JSON object. Allowed actions:
create_folder, create_file, rename, delete, open_app, list_files, none.
Fields:
{{"action":"...", "path":"...", "new_path":"...", "app_name":"...", "content":"..."}}

Rules:
- Use full paths; use ~/Desktop for Desktop requests.
- For a folder/file name inside Desktop, include the full path.
- For list_files, path is the directory.
- For delete, never guess a path; use action=none if unclear.
- Return JSON only, no markdown or explanation.
'''

    try:
        parsed = local_automation_action(user_input)
        if parsed is None:
            raw = router.extract_json(extraction_prompt)
            raw = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)
        action = parsed.get("action")

        if action == "none":
            return None
        if action == "create_folder":
            requested_name = item_name_from_request(user_input)
            path = resolve_automation_path(requested_name or parsed.get("path"))
            return create_folder(path) if path else "Folder ka naam/path nahi mila."
        if action == "create_file":
            path = resolve_automation_path(parsed.get("path"))
            return create_file(path, parsed.get("content", "")) if path else "File ka naam/path nahi mila."
        if action == "rename":
            old_path = resolve_automation_path(parsed.get("path"))
            new_path = resolve_automation_path(parsed.get("new_path"))
            if not old_path or not new_path:
                return "Rename ke liye dono paths chahiye."
            return rename_item(old_path, new_path)
        if action == "delete":
            path = resolve_automation_path(parsed.get("path"))
            if not path:
                return "Delete ke liye exact path chahiye."
            global pending_delete
            pending_delete = path
            return f"Delete ke liye confirmation chahiye: {path}. `/confirm-delete` ya `/cancel-delete` likho."
        if action == "open_app":
            app_name = str(parsed.get("app_name", "")).strip()
            return open_app(app_name) if app_name else "App ka naam nahi mila."
        if action == "list_files":
            path = resolve_automation_path(parsed.get("path", "Desktop"))
            return list_files(path)

        return None
    except Exception as error:
        return f"Automation mein error aayi: {error}"


def detect_and_save_preference(user_input):
    hint_words = ["reply", "bol", "tone", "style", "language", "pasand", "chahiye",
                  "mat", "hamesha", "ab se", "next time", "flirty", "formal", "casual"]
    if not any(word in user_input.lower() for word in hint_words):
        return

    existing_prefs = load_preferences()

    check_prompt = f"""
Existing preferences: {existing_prefs}

User ka naya message: "{user_input}"

Kya ye message JARVIS ko ek instruction/preference/feedback de raha hai future behavior ke liye?
(jaise: reply style, tone, length, language, ya kisi cheez ko pasand/napasand karna)

Agar HAAN:
1. Naya rule likho (max 10 words)
2. Agar ye purani kisi preference se CONFLICT karta hai (jaise "chhota bol" vs "lamba bol"), to purani wali hata dena
3. Response sirf is JSON format mein do: {{"new_rule": "...", "remove": ["purani wali jo hatani hai, agar koi hai"]}}

Agar NAHI, to sirf yeh likho: {{"new_rule": null, "remove": []}}

Sirf JSON likho, kuch aur text mat likho.
"""
    try:
        raw_text = router.extract_json(check_prompt)
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw_text)

        new_rule = parsed.get("new_rule")
        remove_list = parsed.get("remove", [])

        if new_rule:
            updated_prefs = [p for p in existing_prefs if p not in remove_list]
            updated_prefs.append(new_rule)
            replace_preferences(updated_prefs)

            if remove_list:
                print(f"[JARVIS: purani preference hata di: {remove_list}]")
            print(f"[JARVIS ne ye preference yaad rakh li: \"{new_rule}\"]")

    except Exception:
        pass


def handle_command_or_reply(user_input):
    """
    Ek user_input ko process karta hai — commands, automation, preferences,
    ya normal AI reply. Return karta hai: (keep_conversation_going, should_exit_program)
    """
    global voice_mode, wake_word_mode, pending_delete

    is_exit_command = user_input.lower() in ["exit", "quit", "band", "exit jarvis"]
    if (voice_mode or wake_word_mode) and wants_voice_session_exit(user_input):
        is_exit_command = True

    if is_exit_command:
        print("JARVIS: Theek hai bhai, phir milte hain!")
        if voice_mode or wake_word_mode:
            ui_show("speaking")
            speak("Bye.")
            ui_hide()
            voice_mode = False
            wake_word_mode = False
            return False, False
        if orb:
            orb.close()
        return False, True

    command = user_input.lower().strip()

    if (voice_mode or wake_word_mode) and wants_text_mode(user_input):
        speak("Theek hai bhai, ab text mode mein aa gaya. Type karke baat karo.")
        voice_mode = False
        wake_word_mode = False
        ui_hide()
        print("[Voice mode: OFF — text mode active]")
        return False, False

    if command == "/voice":
        voice_mode = not voice_mode
        wake_word_mode = False
        if not voice_mode:
            ui_hide()
        print(f"[Voice mode: {'ON' if voice_mode else 'OFF'}]")
        return False, False

    if command == "/wake":
        wake_word_mode = not wake_word_mode
        voice_mode = False
        ui_show("listening") if wake_word_mode else ui_hide()
        print(f"[Wake word mode: {'ON' if wake_word_mode else 'OFF'} — 'Hey Jarvis' bolo]")
        return False, False

    if command in {"/god", "/auto", "/jarvis", "/jarvis local", "/ollama", "/olla"}:
        selected_provider = (
            "ollama" if command in {"/jarvis", "/jarvis local", "/ollama", "/olla"}
            else ("groq" if command == "/god" else "auto")
        )
        try:
            router.set_provider(selected_provider)
            if selected_provider == "ollama":
                print("JARVIS: Unlimited response mode active.")
            elif selected_provider == "groq":
                print("JARVIS: God mode active.")
            else:
                print(f"JARVIS: Provider {selected_provider} set kar diya.")
        except (RuntimeError, ValueError) as error:
            print(f"JARVIS: {error}")
        return False, False

    if command == "/provider":
        print(f"JARVIS: Abhi {router.provider} use ho raha hai.")
        return False, False

    if command.startswith("/delete "):
        requested_path = command[len("/delete "):].strip()
        pending_delete = resolve_automation_path(requested_path)
        print(f"JARVIS: Delete ke liye confirmation chahiye: {pending_delete}. `/confirm-delete` ya `/cancel-delete` likho.")
        return False, False

    if command == "/cancel-delete":
        pending_delete = None
        print("JARVIS: Delete cancel kar diya.")
        return False, False

    if command == "/confirm-delete":
        if not pending_delete:
            print("JARVIS: Koi pending delete nahi hai.")
            return False, False
        delete_target = pending_delete
        pending_delete = None
        try:
            automation_result = delete_item(delete_target)
        except (OSError, ValueError) as error:
            automation_result = f"Delete nahi ho paya: {error}"
        print("JARVIS:", automation_result)
        if voice_mode or wake_word_mode:
            ui_show("speaking")
            speak(automation_result)
        print()
        return wake_word_mode, False

    # Normal message: preference check + automation + AI reply
    detect_and_save_preference(user_input)

    automation_result = detect_and_run_automation(user_input)
    if automation_result is not None:
        if voice_mode or wake_word_mode:
            ui_state("thinking")
        print("JARVIS:", automation_result)
        if voice_mode or wake_word_mode:
            ui_state("speaking")
            speak(automation_result)
        print()
        router.history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": automation_result},
        ])
        save_history(router.history)
        return wake_word_mode, False

    router.set_system_prompt(build_system_prompt())
    try:
        if voice_mode or wake_word_mode:
            ui_state("thinking")
        response = router.send_message(user_input)
    except (RuntimeError, ValueError) as error:
        print(f"JARVIS: {error}")
        return False, False

    print("JARVIS:", response)
    print()

    if voice_mode or wake_word_mode:
        ui_state("speaking")
        speak(response)

    save_history(router.history)
    return wake_word_mode, False


history = load_history()
router = AIRouter(system_prompt=build_system_prompt(), history=history)

try:
    orb = OrbController()
    atexit.register(orb.close)
except Exception as error:
    orb = None
    print(f"[Orange UI unavailable: {error}]")


def ui_show(state="listening"):
    if orb:
        orb.show()
        orb.set_state(state)


def ui_state(state):
    if orb:
        orb.set_state(state)


def ui_hide():
    if orb:
        orb.hide()


voice_mode = False
wake_word_mode = False
pending_delete = None

print("JARVIS chalu ho gaya! (/god | /jarvis local | /auto | /provider | /voice | /wake | /confirm-delete)\n")

while True:
    if wake_word_mode:
        ui_show("listening")
        if not listen_for_wake_word():
            print("[Wake word mode band kar diya — microphone available nahi hai]")
            wake_word_mode = False
            ui_hide()
            continue
        ui_show("listening")
        ui_state("speaking")
        speak("Haan Sir, boliye.")
        time.sleep(1.5)  # speaker->mic echo settle hone ka time
        ui_state("listening")
        user_input = listen(duration=5)
        if not user_input:
            continue
    elif voice_mode:
        ui_show("listening")
        user_input = listen(duration=5)
        if not user_input:
            continue
    else:
        user_input = input("Tu: ")

    # Conversation loop: ek baar activate hone ke baad, jab tak user chup
    # na ho ya exit na bole, wake-word dobara nahi maangna.
    while True:
        keep_conversation, should_exit_program = handle_command_or_reply(user_input)

        if should_exit_program:
            break

        if keep_conversation:
            ui_show("listening")
            follow_up = listen(duration=6)
            if not follow_up:
                break
            user_input = follow_up
            continue

        break

    if should_exit_program:
        break