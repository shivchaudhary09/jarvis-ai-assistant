import os
import subprocess


def _clean_path(path):
    path = os.path.abspath(os.path.expanduser(path))
    parent, name = os.path.dirname(path), os.path.basename(path).strip()
    return os.path.join(parent, name)


def create_folder(path):
    """Create a folder at the specified path."""
    path = _clean_path(path)
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError as error:
        raise PermissionError(
            "Desktop access denied. Run JARVIS from Terminal.app or grant Desktop access "
            "to Terminal / VS Code in macOS System Settings > Privacy & Security > Files and Folders."
        ) from error
    if not os.path.isdir(path):
        raise OSError(f"Could not verify folder creation: {path}")
    return f"Folder created: {path}"


def create_file(path, content=""):
    """Create a file with optional content at the specified path."""
    path = _clean_path(path)
    parent = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
    except PermissionError as error:
        raise PermissionError(
            "Desktop access denied. Run JARVIS from Terminal.app or grant Desktop access "
            "to Terminal / VS Code in macOS System Settings > Privacy & Security > Files and Folders."
        ) from error
    if not os.path.isfile(path):
        raise OSError(f"Could not verify file creation: {path}")
    return f"File created: {path}"


def rename_item(old_path, new_path):
    """Rename a file or directory."""
    old_path = os.path.abspath(os.path.expanduser(old_path))
    new_path = os.path.abspath(os.path.expanduser(new_path))
    os.rename(old_path, new_path)
    if not os.path.exists(new_path):
        raise OSError(f"Could not verify rename: {new_path}")
    return f"Renamed: {old_path} -> {new_path}"


def delete_item(path):
    """Safely move an item to macOS Finder Trash."""
    path = os.path.realpath(os.path.expanduser(path))
    # Match existing item case-insensitively if needed
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
        raise ValueError("Safety protection: Cannot delete home folder, Desktop, or root directory.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File or directory not found: {path}")

    # Use Finder Trash operation for safe, recoverable deletion
    escaped_path = path.replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped_path}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        raise OSError(f"Finder Trash operation failed: {detail.strip()}") from error

    if os.path.exists(path):
        raise OSError(f"Item still exists: {path}")
    return f"Moved to Trash: {path}"


def open_app(app_name):
    """Launch a macOS application by name."""
    try:
        subprocess.run(
            ["open", "-a", app_name],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        return f"Failed to open {app_name}: {detail.strip()}"
    return f"Opened {app_name}"


def list_files(directory):
    """List directory contents."""
    directory = os.path.abspath(os.path.expanduser(directory))
    items = os.listdir(directory)
    return "\n".join(items) if items else "No files found"
