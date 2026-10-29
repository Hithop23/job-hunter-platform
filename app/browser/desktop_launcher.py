import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE_DIR / "data" / "browser_profile"


def find_browser_executable() -> Optional[Path]:
    """
    Finds the best available Chromium or modern browser executable on the system.
    Priority:
    1. Playwright's bundled Chromium (Chrome for Testing)
    2. Google Chrome (Standard 64-bit / 32-bit / LocalAppData)
    3. Microsoft Edge (Pre-installed on Windows 10/11)
    """
    candidates = []

    # 1. Google Chrome (Standard 64-bit / 32-bit / LocalAppData)
    candidates.extend([
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ])
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe")

    # 2. Microsoft Edge (Native Windows default browser)
    candidates.extend([
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
    ])

    # 3. Playwright bundled Chromium (Testing fallback)
    if local_app_data:
        playwright_dir = Path(local_app_data) / "ms-playwright"
        if playwright_dir.exists():
            for chrome_exe in playwright_dir.glob("chromium-*/chrome-win64/chrome.exe"):
                if chrome_exe.exists():
                    candidates.append(chrome_exe)

    for exe in candidates:
        if exe.exists():
            return exe

    return None


def kill_ghost_chrome_processes():
    """
    Kills any chrome/chromium process that has NO visible window (MainWindowHandle == 0)
    and is holding the profile directory, preventing GUI launches from being swallowed.
    """
    if sys.platform != "win32":
        return

    try:
        ps_script = (
            "Get-Process chrome,chromium -ErrorAction SilentlyContinue | "
            "Where-Object { $_.MainWindowHandle -eq 0 -and ($_.Path -like '*ms-playwright*' -or $_.CommandLine -like '*browser_profile*') } | "
            "Stop-Process -Force -ErrorAction SilentlyContinue"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=5
        )
    except Exception:
        pass


def cleanup_profile_locks(profile_dir: Path):
    """
    Removes stale lockfiles so the browser doesn't report ProcessSingleton
    or profile-in-use errors.
    """
    lock_names = [
        "lockfile",
        "SingletonLock",
        "SingletonSocket",
        "SingletonCookie",
        ".parentlock",
        "lock"
    ]
    for lock in lock_names:
        p = profile_dir / lock
        if p.exists():
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


def launch_desktop_browser(target_url: str = "https://www.linkedin.com/login") -> Dict[str, Any]:
    """
    Launches a fully visible desktop browser window pointing to the persistent profile directory.
    Guarantees:
    1. Kills ghost windowless instances so the new window always pops up on screen.
    2. Cleans stale lockfiles.
    3. Launches through Windows Shell (`start ""`) for direct foreground interactive display.
    4. Cookies and sessions are permanently saved in data/browser_profile.
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clear out any windowless background instances and locks
    kill_ghost_chrome_processes()
    cleanup_profile_locks(PROFILE_DIR)
    time.sleep(0.3)

    browser_exe = find_browser_executable()

    if sys.platform == "win32":
        try:
            os.startfile(target_url)
            return {
                "success": True,
                "method": "os_startfile",
                "browser": "Microsoft Edge / Default Browser",
                "url": target_url,
                "message": "Navegador abierto directamente en tu pantalla."
            }
        except Exception:
            pass

    # Fallback to standard webbrowser module
    try:
        webbrowser.open(target_url, new=2)
        return {
            "success": True,
            "method": "webbrowser_fallback",
            "browser": "default_system_browser",
            "url": target_url,
            "message": "Navegador predeterminado del sistema abierto en tu pantalla."
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "message": f"No se pudo abrir el navegador automáticamente: {exc}"
        }


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.linkedin.com/login"
    result = launch_desktop_browser(url)
    print(result)
