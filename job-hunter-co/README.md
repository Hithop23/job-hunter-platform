# JOB-HUNTER-CO

Agente automatizado de búsqueda, clasificación, preparación y seguimiento de
postulaciones laborales para Colombia.

## Requisitos

- Python 3.12+ (probado con 3.14)
- Node.js LTS (portable, instalado en `tools/node` por el setup)

## Uso rápido

```powershell
# desde la raíz del proyecto
.venv\Scripts\python.exe -m app.main scan
.venv\Scripts\python.exe -m app.main prepare
.venv\Scripts\python.exe -m app.main autopilot --i-confirm-autopilot
.venv\Scripts\python.exe -m app.main serve
.venv\Scripts\python.exe -m app.main export --out data/candidaturas.csv
```

## Modos de ejecución (Módulo 15)

- `scan` — solo busca vacantes.
- `prepare` — busca, analiza compatibilidad y genera CV/carta.
- `autopilot` — además envía candidaturas donde el sitio lo permita.
  Requiere `JHC_AUTOPILOT_ENABLED=true` en `.env` **y** la bandera
  `--i-confirm-autopilot`. Ante CAPTCHA, 2FA o preguntas sensibles el sistema
  se detiene y solicita intervención humana.

## Seguridad

El sistema nunca: salta CAPTCHAs, evade controles anti-bot, inventa datos del
candidato, ni registra credenciales en logs.

## Estado de fases

- [x] F1 — Esqueleto: modelos, CLI, logging, tests
- [ ] F2 — Perfil + motor de compatibilidad
- [ ] F3 — Adapters de fuentes (ATS, SPE, SENA, CNSC, LinkedIn)
- [ ] F4 — CV ATS + cartas (PREPARE)
- [ ] F5 — Autopilot de formularios
- [ ] F6 — Dashboard + API + export
