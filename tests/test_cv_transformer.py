import io
from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app
from app.cv.cv_transformer import CVTransformer

client = TestClient(app)

def test_cv_generation_api():
    payload = {
        "name": "Maria Rodriguez",
        "email": "maria@example.com",
        "phone": "+57 310 987 6543",
        "city": "Medellín",
        "headline": "Ingeniera de Sistemas | Cloud & DevOps",
        "summary": "Especialista en infraestructura cloud y automatización de despliegues.",
        "technical_skills": {"destacadas": ["AWS", "Docker", "Linux", "Python"]},
        "experience": [
            {
                "role": "Ingeniera Cloud",
                "company": "CloudTech",
                "period": "2023 - 2025",
                "achievements": ["Reducción de costos de infraestructura en un 30%."]
            }
        ],
        "education": [
            {
                "degree": "Ingeniería de Sistemas",
                "institution": "Universidad de Antioquia",
                "period": "2018 - 2023",
                "status": "Graduado"
            }
        ],
        "certifications": [
            {"title": "AWS Certified Solutions Architect", "issuer": "Amazon", "date": "2024"}
        ],
        "languages": [
            {"language": "Español", "level": "Nativo"},
            {"language": "Inglés", "level": "B2"}
        ]
    }

    r = client.post("/api/cv/generate", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "SUCCESS"
    assert "pdf_download_url" in data
    assert "docx_download_url" in data

    # Verify download endpoints
    r_pdf = client.get(data["pdf_download_url"])
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert len(r_pdf.content) > 1000

    r_docx = client.get(data["docx_download_url"])
    assert r_docx.status_code == 200
    assert "wordprocessingml" in r_docx.headers["content-type"]
    assert len(r_docx.content) > 1000

def test_cv_upload_text():
    sample_text = b"""
    MARIA RODRIGUEZ
    Ingeniera de Sistemas | Soporte TI
    Email: maria@example.com
    Tel: +57 310 987 6543
    Medellin, Colombia
    
    PERFIL PROFESIONAL
    Ingeniera de sistemas con experiencia en soporte y redes.
    
    COMPETENCIAS
    Soporte TI, Linux, Windows 11, Redes LAN, Python
    
    EXPERIENCIA LABORAL
    Analista de Soporte TI - Tech SAS
    2023 - 2025
    - Mantenimiento y soporte a usuarios.
    """

    file_tuple = ("cv_maria.txt", io.BytesIO(sample_text), "text/plain")
    r = client.post("/api/cv/upload", files={"file": file_tuple})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "SUCCESS"
    assert data["parsed_profile"]["name"] == "MARIA RODRIGUEZ"
    assert data["parsed_profile"]["email"] == "maria@example.com"
