import re
from typing import Dict, Any, Optional


class FieldMapper:
    """
    Intelligently maps candidate profile attributes to HTML form inputs,
    supporting English and Spanish labels, placeholders, and attributes.
    """

    PATTERNS = {
        "full_name": [
            r"nombre[_\s-]*completo",
            r"full[_\s-]*name",
            r"^nombre$",
            r"^name$",
            r"applicant[_\s-]*name",
            r"candidate[_\s-]*name",
        ],
        "first_name": [
            r"first[_\s-]*name",
            r"primer[_\s-]*nombre",
            r"nombres?",
            r"given[_\s-]*name",
            r"fname",
            r"forename",
        ],
        "last_name": [
            r"last[_\s-]*name",
            r"apellidos?",
            r"primer[_\s-]*apellido",
            r"family[_\s-]*name",
            r"surname",
            r"lname",
        ],
        "email": [
            r"correo",
            r"email",
            r"e-mail",
            r"correo[_\s-]*electr[oó]nico",
            r"mail",
        ],
        "phone": [
            r"phone[_\s-]*number",
            r"tel[eé]fono",
            r"celular",
            r"phone",
            r"m[oó]vil",
            r"mobile",
            r"telephone",
            r"whatsapp",
        ],
        "prefix_phone": [
            r"prefix[_\s-]*phone",
            r"prefijo",
            r"c[oó]digo[_\s-]*pa[ií]s",
        ],
        "city": [
            r"ciudad",
            r"city",
            r"municipio",
            r"town",
            r"localidad",
            r"location",
        ],
        "address": [
            r"direcci[oó]n",
            r"address",
            r"domicilio",
            r"residencia",
        ],
        "country": [
            r"pa[ií]s",
            r"country",
            r"naci[oó]n",
            r"nacionalidad",
        ],
        "linkedin": [
            r"linkedin",
            r"perfil[_\s-]*de[_\s-]*linkedin",
            r"linkedin[_\s-]*url",
            r"urls\[linkedin\]",
        ],
        "resume": [
            r"hoja[_\s-]*de[_\s-]*vida",
            r"curr[ií]culum",
            r"cv",
            r"resume",
            r"adjuntar[_\s-]*cv",
            r"upload[_\s-]*resume",
            r"cvinputfile",
            r"fileincludecv",
            r"attach[_\s-]*resume",
        ],
        "cover_letter": [
            r"carta[_\s-]*de[_\s-]*presentaci[oó]n",
            r"cover[_\s-]*letter",
            r"carta[_\s-]*motivaci[oó]n",
            r"mensaje",
            r"resumen",
            r"perfil[_\s-]*profesional",
            r"additional[_\s-]*info",
            r"comments",
        ],
        "terms": [
            r"terms",
            r"consent",
            r"accepted",
            r"condiciones",
            r"terminos",
            r"privacidad",
            r"privacy",
        ],
        "document_number": [
            r"c[eé]dula",
            r"documento",
            r"n[uú]mero[_\s-]*documento",
            r"identificaci[oó]n",
            r"dni",
            r"cc",
            r"identification[_\s-]*number",
            r"id[_\s-]*number",
            r"national[_\s-]*id",
            r"num[_\s-]*doc",
        ],
        "document_type": [
            r"tipo[_\s-]*documento",
            r"tipo[_\s-]*identificaci[oó]n",
            r"doc[_\s-]*type",
            r"id[_\s-]*type",
        ],
        "password": [
            r"contrase[ñn]a",
            r"password",
            r"clave",
            r"pass",
            r"pwd",
        ],
        "confirm_password": [
            r"confirmar[_\s-]*contrase[ñn]a",
            r"confirm[_\s-]*password",
            r"repetir[_\s-]*contrase[ñn]a",
            r"re[_\s-]*password",
            r"retype[_\s-]*password",
        ],
        "username": [
            r"usuario",
            r"username",
            r"user[_\s-]*name",
            r"login",
        ],
    }

    @classmethod
    def identify_field(cls, name_attr: str, id_attr: str, label_text: str, placeholder: str) -> Optional[str]:
        combined = f"{name_attr} {id_attr} {label_text} {placeholder}".lower()
        for field_type, patterns in cls.PATTERNS.items():
            for p in patterns:
                if re.search(p, combined):
                    return field_type
        return None

    @classmethod
    def get_candidate_value(cls, field_type: str, profile: Dict[str, Any], cv_path: str = None, cover_letter: str = None) -> Any:
        name_parts = profile.get("name", "").split()
        first_name = " ".join(name_parts[:2]) if len(name_parts) >= 2 else profile.get("name", "")
        last_name = " ".join(name_parts[2:]) if len(name_parts) >= 3 else ""

        raw_phone = profile.get("phone", "")
        clean_phone = re.sub(r"[^\d]", "", raw_phone)
        if clean_phone.startswith("57") and len(clean_phone) > 10:
            local_phone = clean_phone[2:]
        else:
            local_phone = clean_phone

        portal_pwd = profile.get("portal_credentials", {}).get("password", "")
        portal_usr = profile.get("portal_credentials", {}).get("username", "")

        values = {
            "full_name": profile.get("name", ""),
            "first_name": first_name,
            "last_name": last_name,
            "email": profile.get("email", ""),
            "phone": local_phone or "",
            "prefix_phone": "57",
            "city": profile.get("city", "Colombia"),
            "address": profile.get("location") or profile.get("city", "Colombia"),
            "country": profile.get("country", "Colombia"),
            "document_number": profile.get("cedula") or profile.get("document_number", ""),
            "document_type": "CC",
            "password": portal_pwd,
            "confirm_password": portal_pwd,
            "username": portal_usr,
            "linkedin": profile.get("linkedin", ""),
            "resume": cv_path,
            "cover_letter": cover_letter or profile.get("summary", ""),
            "terms": True,
        }
        return values.get(field_type)
