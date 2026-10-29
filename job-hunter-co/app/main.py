from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from app.config import load_settings
from app.db import init_db, make_engine, make_session_factory
from app.logging_config import setup_logging
from app.models import Application, Job
from app.runner import AutopilotNotConfirmed, Mode, run_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-hunter-co",
        description=(
            "Agente de búsqueda y postulación laboral para Colombia. "
            "La automatización maximiza oportunidades relevantes, nunca spam."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Solo busca vacantes")
    p_scan.add_argument("--sources", help="Fuentes separadas por coma (opcional)")

    p_prepare = sub.add_parser(
        "prepare", help="Busca + analiza + genera CV + prepara candidatura"
    )
    p_prepare.add_argument("--sources")

    p_auto = sub.add_parser(
        "autopilot",
        help="Busca + prepara + envía donde el sitio lo permita (con límites)",
    )
    p_auto.add_argument("--sources")
    p_auto.add_argument(
        "--i-confirm-autopilot",
        action="store_true",
        help="Confirmación explícita e informada del usuario (obligatoria)",
    )

    p_serve = sub.add_parser("serve", help="Levanta el dashboard (API + web)")
    p_serve.add_argument("--port", type=int, default=8000)

    p_export = sub.add_parser("export", help="Exporta candidaturas a CSV")
    p_export.add_argument(
        "--out", default="data/applications_export.csv", help="Ruta del CSV"
    )
    return parser


def _export_csv(session, out_path: Path) -> int:
    """Exporta todas las candidaturas a CSV (requisito final 14)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "application_id",
        "job_id",
        "company",
        "position",
        "url",
        "status",
        "cv_version",
        "submitted_at",
        "source",
        "notes",
    ]
    applications = (
        session.query(Application).join(Job, Application.job_id == Job.id).all()
    )
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for app in applications:
            status = (
                app.status.value if hasattr(app.status, "value") else app.status
            )
            writer.writerow(
                [
                    app.id,
                    app.job_id,
                    app.job.company,
                    app.job.title,
                    app.job.url,
                    status,
                    app.cv_version or "",
                    app.submitted_at or "",
                    app.source or "",
                    (app.notes or "").replace("\n", " "),
                ]
            )
    return len(applications)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    setup_logging(settings.resolve(settings.logs_dir))

    if args.command == "serve":
        import uvicorn

        from app.api.app import create_app

        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)
        return 0

    engine = make_engine(settings.resolve(settings.db_path))
    init_db(engine)
    session_factory = make_session_factory(engine)

    with session_factory() as session:
        if args.command == "export":
            out_path = settings.resolve(args.out)
            count = _export_csv(session, out_path)
            print(f"Exportadas {count} candidaturas a {out_path}")
            return 0

        mode = {
            "scan": Mode.SCAN,
            "prepare": Mode.PREPARE,
            "autopilot": Mode.AUTOPILOT,
        }[args.command]
        sources = (
            [s.strip() for s in args.sources.split(",") if s.strip()]
            if args.sources
            else None
        )
        try:
            summary = run_mode(
                mode,
                settings,
                session,
                sources=sources,
                confirm_autopilot=getattr(args, "i_confirm_autopilot", False),
            )
        except AutopilotNotConfirmed as exc:
            print(f"DETENIDO: {exc}", file=sys.stderr)
            return 2

    print(
        f"[{summary.mode}] nuevas={summary.jobs_discovered} "
        f"duplicadas={summary.duplicates} errores={summary.errors} "
        f"fuentes={','.join(summary.sources_run) or 'ninguna'} | "
        f"prioridad alta={summary.matched_high} revisión={summary.matched_review} "
        f"baja={summary.matched_low} marcadas={summary.flagged}"
    )
    if summary.message:
        print(f"NOTA: {summary.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
