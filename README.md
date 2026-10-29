# JOB-HUNTER-CO 🇨🇴
### Agente Automatizado de Búsqueda, Filtrado, Preparación de CV ATS y Postulación Laboral para Colombia

**JOB-HUNTER-CO** es una plataforma de software local diseñada para automatizar de manera ética y rigurosa la búsqueda, compatibilidad, adaptación de hojas de vida ATS y seguimiento de oportunidades laborales en Colombia, configurada especialmente para el perfil técnico y real de **Julian David Diaz Medina**.

---

## 🎯 Perfil del Candidato

- **Nombre:** Julian David Diaz Medina
- **Perfil:** Técnico en Sistemas Teleinformáticos (SENA)
- **Ubicación:** Valledupar, Cesar, Colombia
- **Contacto:** `+57 320 684 1270` | `maestrecs92@gmail.com` | [LinkedIn](https://www.linkedin.com/in/julian-diaz-soporte-ti)
- **Especialidad:** Soporte técnico presencial y remoto (AnyDesk, TeamViewer), diagnóstico de hardware y software, mantenimiento preventivo/correctivo, sistemas operativos Windows y Linux/Ubuntu, configuración de impresoras y periféricos, redes básicas y cableado, fundamentos de ciberseguridad (Cisco Endpoint Security), y análisis exploratorio con Python.
- **Principio Fundamental:** **NUNCA inventar información.** Toda postulación, CV y carta de presentación contiene única y exclusivamente datos verídicos y comprobables.

---

## 🏗️ Arquitectura del Sistema (18 Módulos)

```
job-hunter-co/
├── app/
│   ├── api/                     # FastAPI backend & Dashboard SPA
│   │   ├── main.py              # Servidor API y montaje de rutas
│   │   ├── dashboard.html       # Interfaz de usuario interactiva
│   │   ├── routes_jobs.py       # Descubrimiento y escaneo de vacantes
│   │   ├── routes_applications.py # Tracking, preparación ATS y exportación CSV
│   │   ├── routes_hil.py        # Cola de revisión humana (Human-in-the-Loop)
│   │   └── routes_stats.py      # Métricas y analíticas en tiempo real
│   ├── adapters/                # Adaptadores de fuentes de empleo
│   │   ├── base.py              # BaseJobAdapter y deduplicación
│   │   ├── sena/                # Agencia Pública de Empleo SENA
│   │   ├── spe/                 # Servicio Público de Empleo Colombia
│   │   ├── cnsc/                # Empleo Público CNSC / SIMO (Nivel Técnico/Asistencial)
│   │   ├── companies/           # ATS de Grandes Empresas (Bancolombia, Claro, Nutresa, etc.)
│   │   ├── computrabajo/        # Computrabajo Colombia
│   │   ├── indeed/              # Indeed Colombia
│   │   └── linkedin/            # LinkedIn Empleos Colombia (búsqueda pública)
│   ├── matching/                # Motor de Compatibilidad y Scoring
│   │   └── matcher.py           # Ponderación (Skills 40%, Edu 20%, Exp 20%, Loc 10%, Keywords 10%)
│   ├── cv/                      # Motor de Generación ATS
│   │   ├── cv_generator.py      # Generador de CV PDF ReportLab ATS reordenado por keywords
│   │   └── cover_letter.py      # Cartas de presentación personalizadas (<250 palabras)
│   ├── browser/                 # Autopilot de Formularios con Playwright
│   │   ├── browser_manager.py   # Navegador Chromium persistente y screenshots
│   │   └── field_mapper.py      # Mapeo semántico de campos de formulario
│   ├── storage/                 # Persistencia en Base de Datos
│   │   ├── models.py            # Modelos SQLAlchemy (Job, Application, HumanReviewItem, Logs)
│   │   ├── database.py          # SQLite connection
│   │   └── repository.py        # Deduplicación compuesta y control de tasas
│   └── notifications/           # Notificaciones del sistema
│       └── notifier.py          # Alertas de vacantes top e intervenciones requeridas
├── data/
│   ├── profile.json             # Perfil auténtico verificado
│   ├── companies.json           # Directorio de empresas colombianas y sus portales
│   ├── keywords.json            # Diccionario de cargos, skills, exclusiones y pesos
│   └── applications.db          # Base de datos SQLite
├── cv/
│   ├── master_cv.pdf            # Hoja de vida maestra original
│   └── variants/                # Hojas de vida PDF generadas para cada vacante
├── frontend/                    # Estructura React + Vite (opcional)
├── logs/                        # Screenshots y auditoría
├── tests/                       # Suite completa de pruebas unitarias
└── run.py                       # Lanzador unificado de la aplicación
```

---

## 🛡️ Principios de Seguridad y Human-in-the-Loop

1. **Sin Evasión Ilegal ni Spammeo:**
   - **NO** se evaden CAPTCHAs, ni Cloudflare, ni sistemas anti-bot.
   - Si se detecta un CAPTCHA, 2FA, prueba técnica, o pregunta salarial compleja, el navegador se pausa, toma una captura de pantalla y envía la postulación a la **Cola de Revisión Humana**.
2. **Control de Tasa y Cuotas:**
   - Máximo 10 peticiones por dominio por hora.
   - Máximo 50 postulaciones por día.
   - Intervalos de espera aleatorios (jitter) entre acciones para proteger la IP del usuario.
3. **Filtro Estricto de Seniority:**
   - Vacantes con requisitos de Senior, Lead, Gerente o tarjeta profesional de ingeniería obligatoria son descalificadas automáticamente (`does_not_meet_required_requirement = True`).

---

## 🚀 Instrucciones de Puesta en Marcha

### 1. Activar el entorno virtual e iniciar la aplicación
En la terminal (PowerShell):
```powershell
.\.venv\Scripts\activate
python run.py
```
*Esto iniciará el servidor FastAPI en el puerto 8000 y abrirá automáticamente el Dashboard en tu navegador:*
👉 **http://localhost:8000**

### 2. Modos de Ejecución Disponibles en el Panel
- **SCAN:** Busca y detecta vacantes nuevas sin generar archivos.
- **PREPARE:** Busca vacantes, evalúa compatibilidad, genera una versión específica del CV ATS en PDF en `cv/variants/` y redacta la carta de presentación personalizada.
- **AUTOPILOT:** Mapea el formulario en el portal web mediante Playwright en modo seguro (Dry-Run / Envío verificado) y solicita confirmación humana ante cualquier bloqueo o pregunta no estándar.

### 3. Ejecutar las Pruebas Unitarias Obligatorias
```powershell
.\.venv\Scripts\python -m pytest -v tests/test_all_modules.py
```
Todos los 10 tests de validación pasarán satisfactoriamente:
- Normalización canónica de vacantes
- Detección y prevención de duplicados (por clave compuesta y hash)
- Motor de scoring ponderado
- Detección de requisitos excluyentes y penalizaciones Senior
- Extracción honesta de keywords sin inventar datos
- Mapeo semántico de campos de formulario
- Ciclo de vida y tracking de postulaciones
- Control de límites por dominio y cuota diaria
- Pausa obligatoria e intervención en la cola Human-in-the-Loop
- Garantía de veracidad de datos del candidato
