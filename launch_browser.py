"""
JOB-HUNTER-CO: Lanzador de Navegador Interactivo con Perfil Persistente.
Abre una ventana visible de Chromium/Chrome usando 'data/browser_profile'.
Inicia sesión en LinkedIn, Computrabajo, SIMO o cualquier portal para que
tus cookies y sesiones queden guardadas de forma permanente.
"""
import sys
from pathlib import Path

# Fix Windows console encoding safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.browser.desktop_launcher import launch_desktop_browser, find_browser_executable, PROFILE_DIR


def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.linkedin.com/login"

    print("=" * 65)
    print("  JOB-HUNTER-CO: NAVEGADOR DE AUTENTICACION Y SESIONES")
    print("=" * 65)
    print(f"[INFO] URL de inicio: {target_url}")
    print(f"[INFO] Directorio de perfil persistente: {PROFILE_DIR}")

    exe = find_browser_executable()
    if exe:
        print(f"[INFO] Navegador detectado: {exe.name} ({exe})")
    else:
        print("[AVISO] Usando navegador predeterminado del sistema.")

    print("\n[ACCION] Abriendo ventana en tu pantalla principal...")
    res = launch_desktop_browser(target_url)

    if res.get("success"):
        print(f"[EXITO] {res.get('message', 'Ventana abierta.')}")
        print("\n[INSTRUCCIONES]:")
        print("  1. Inicia sesion en tus cuentas o completa la accion requerida.")
        print("  2. Todas tus cookies y credenciales se guardan automaticamente.")
        print("  3. Cuando termines, simplemente cierra la ventana del navegador.")
    else:
        print(f"[ERROR] No se pudo abrir: {res.get('error')}")

    print("=" * 65)


if __name__ == "__main__":
    main()
