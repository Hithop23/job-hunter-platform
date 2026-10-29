"""
JOB-HUNTER-CO: Entrypoint launcher script.
Runs the local web server and opens the dashboard in the browser.
"""
import sys
import webbrowser
import uvicorn
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def main():
    print("=" * 60)
    print("INICIANDO JOB-HUNTER-CO")
    print("Agente automatizado de busqueda y postulacion laboral para Colombia")
    print("Candidato: Julian David Diaz Medina (Tecnico en Sistemas Teleinformaticos)")
    print("Panel de Control: http://localhost:8000")
    print("Documentacion API: http://localhost:8000/docs")
    print("=" * 60)

    try:
        # Open browser automatically after launch
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass

    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
