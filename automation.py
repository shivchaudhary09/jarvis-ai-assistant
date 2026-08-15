import os
import subprocess

def _clean_path(path):
    path = os.path.abspath(os.path.expanduser(path))
    parent, name = os.path.dirname(path), os.path.basename(path).strip()
    return os.path.join(parent, name)

def create_folder(path):
    path = _clean_path(path)
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError as error:
        raise PermissionError(
            "Desktop access process ko deny hai. JARVIS ko normal Terminal.app se run karo "
            "ya Terminal/VS Code ko Files & Folders > Desktop access do."
        ) from error
    if not os.path.isdir(path):
        raise OSError(f"Folder verify nahi ho paya: {path}")
    return f"Folder ban gaya: {path}"

def create_file(path, content=""):
    path = _clean_path(path)
    parent = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
    except PermissionError as error:
        raise PermissionError(
            "Desktop access process ko deny hai. JARVIS ko normal Terminal.app se run karo "
            "ya Terminal/VS Code ko Files & Folders > Desktop access do."
        ) from error
    if not os.path.isfile(path):
        raise OSError(f"File verify nahi ho payi: {path}")
    return f"File ban gayi: {path}"

def rename_item(old_path, new_path):
    old_path = os.path.abspath(os.path.expanduser(old_path))
    new_path = os.path.abspath(os.path.expanduser(new_path))
    os.rename(old_path, new_path)
    if not os.path.exists(new_path):
        raise OSError(f"Rename verify nahi ho paya: {new_path}")
    return f"Rename ho gaya: {old_path} -> {new_path}"

def delete_item(path):
    path = os.path.realpath(os.path.expanduser(path))
    # macOS paths are case-sensitive on many setups; match an existing item
    # by name so "testjarvis" can target an actual "TestJarvis" folder.
    if not os.path.exists(path):
        parent, name = os.path.dirname(path), os.path.basename(path)
        if os.path.isdir(parent):
            for entry in os.listdir(parent):
                if entry.strip().casefold() == name.strip().casefold():
                    path = os.path.join(parent, entry)
                    break
    protected_paths = {
        os.path.realpath(os.path.expanduser("~")),
        os.path.realpath(os.path.expanduser("~/Desktop")),
        os.path.realpath("/"),
    }
    if path in protected_paths:
        raise ValueError("Safety ke liye home folder, Desktop, ya root delete nahi kar sakte.")
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    # Desktop has a macOS ACL that can deny direct child deletion even when
    # the app has Files & Folders access. Finder's Trash operation handles it
    # correctly and remains recoverable.
    escaped_path = path.replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped_path}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        raise OSError(f"Finder Trash operation fail hui: {detail.strip()}") from error

    if os.path.exists(path):
        raise OSError(f"Item abhi bhi exist karta hai: {path}")
    return f"Trash mein move kar diya: {path}"

def open_app(app_name):
    try:
        result = subprocess.run(
            ["open", "-a", app_name],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        return f"{app_name} nahi khul paya: {detail.strip()}"
    return f"{app_name} khol diya"

def list_files(directory):
    directory = os.path.abspath(os.path.expanduser(directory))
    items = os.listdir(directory)
    return "\n".join(items) if items else "Koi file nahi mili"
