from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd


def normalize_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip().lower()
    value = "".join(
        c for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", value)


def normalize_phone(value):
    if pd.isna(value):
        return None
    digits = "".join(re.findall(r"\d", str(value)))
    if digits.startswith("0057") and len(digits) == 14:
        digits = digits[4:]
    elif digits.startswith("57") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("3"):
        return f"+57{digits}"
    return digits


def normalize_city(value):
    value = normalize_text(value)
    if value is None:
        return None
    value = value.replace(".", "")
    aliases = {
        "bogota dc": "bogota",
        "bogota d c": "bogota",
        "cartagena de indias": "cartagena",
        "rio negro": "rionegro",
        "sta marta": "santa marta",
        "b/quilla": "barranquilla",
    }
    return aliases.get(value, value)


def normalize_model(value):
    value = normalize_text(value)
    if value is None:
        return None
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\b2026\b", "", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date_status(value):
    """Classify dates using the same deterministic policy as dbt staging."""
    if pd.isna(value) or str(value).strip() == "":
        return "MISSING"

    text = str(value).strip()
    date_part = text[:10]

    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date_part):
        try:
            datetime.strptime(date_part, "%Y-%m-%d")
        except ValueError:
            return "INVALID"
        return "VALID"

    if re.fullmatch(r"[0-9]{2}-[0-9]{2}-[0-9]{4}", text):
        try:
            datetime.strptime(text, "%d-%m-%Y")
        except ValueError:
            return "INVALID"
        return "VALID"

    slash_match = re.match(r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})(?:[ T].*)?$", text)
    if slash_match:
        first, second, year = map(int, slash_match.groups())
        if first <= 12 and second <= 12:
            return "AMBIGUOUS"
        fmt = "%d/%m/%Y" if first > 12 else "%m/%d/%Y"
        try:
            datetime.strptime(f"{first}/{second}/{year}", fmt)
        except ValueError:
            return "INVALID"
        return "VALID"

    return "INVALID"


def date_format(value):
    if pd.isna(value) or str(value).strip() == "":
        return "OTHER"
    text = str(value).strip()
    if re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        return "ISO"
    if re.fullmatch(r"[0-9]{2}-[0-9]{2}-[0-9]{4}", text):
        return "DD-MM-YYYY"
    if re.match(r"^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", text):
        return "SLASH"
    return "OTHER"


def profile(input_dir: Path) -> dict:
    leads = pd.read_csv(input_dir / "leads.csv")
    catalog = pd.read_csv(input_dir / "catalogo_motos.csv")
    advisors = pd.read_csv(input_dir / "asesores.csv")
    history = pd.read_csv(input_dir / "historico_cierres.csv")
    conversations = json.loads(
        (input_dir / "conversaciones.json").read_text(encoding="utf-8")
    )

    leads["phone_norm"] = leads["telefono"].map(normalize_phone)
    leads["channel_norm"] = leads["canal"].map(normalize_text)
    leads["state_norm"] = leads["estado_gestion"].map(normalize_text)
    leads["city_norm"] = leads["ciudad"].map(normalize_city)
    leads["model_norm"] = leads["modelo_interes_texto"].map(normalize_model)
    leads["fecha_registro_format"] = leads["fecha_registro"].map(date_format)
    leads["fecha_registro_parse_status"] = leads["fecha_registro"].map(parse_date_status)
    leads["fecha_primer_contacto_parse_status"] = leads[
        "fecha_primer_contacto"
    ].map(parse_date_status)

    catalog["canonical_name"] = catalog["marca"] + " " + catalog["linea"]
    catalog["model_norm"] = catalog["canonical_name"].map(normalize_model)
    canonical_models = set(catalog["model_norm"])

    phone_groups = (
        leads.groupby("phone_norm", dropna=True)
        .agg(
            rows=("lead_id", "size"),
            companies=("empresa_id", "nunique"),
            channels=("channel_norm", "nunique"),
        )
    )
    within_company = (
        leads.groupby(["empresa_id", "phone_norm"], dropna=True)
        .size()
    )

    conv_df = pd.DataFrame(
        {
            "conversacion_id": c["conversacion_id"],
            "lead_id": c["lead_id"],
            "n_mensajes": len(c.get("mensajes", [])),
        }
        for c in conversations
    )

    history["closed"] = (history["desenlace"] == "Cerrado").astype(int)
    contacted = history[history["desenlace"] != "Sin gestión"]

    summary = {
        "leads": {
            "rows": len(leads),
            "unique_lead_ids": leads["lead_id"].nunique(),
            "duplicate_lead_ids": sorted(
                leads.loc[
                    leads.duplicated("lead_id", keep=False), "lead_id"
                ].unique().tolist()
            ),
            "nulls": leads.isna().sum().to_dict(),
            "normalized_channel_counts": leads["channel_norm"]
                .value_counts(dropna=False).to_dict(),
            "normalized_state_counts": leads["state_norm"]
                .value_counts(dropna=False).to_dict(),
            "fecha_registro_formats": leads["fecha_registro_format"]
                .value_counts(dropna=False).to_dict(),
            "fecha_registro_parse_status": leads["fecha_registro_parse_status"]
                .value_counts(dropna=False).to_dict(),
            "fecha_primer_contacto_parse_status": leads["fecha_primer_contacto_parse_status"]
                .value_counts(dropna=False).to_dict(),
            "raw_city_variants": leads["ciudad"].nunique(),
            "canonical_city_count": leads["city_norm"].nunique(),
            "raw_model_variants": leads["modelo_interes_texto"].nunique(),
            "basic_exact_catalog_matches": int(
                leads["model_norm"].isin(canonical_models).sum()
            ),
            "invalid_phone_rows": int(
                (~leads["phone_norm"].str.match(r"^\+573\d{9}$", na=False)).sum()
            ),
            "global_duplicate_phone_groups": int((phone_groups["rows"] > 1).sum()),
            "cross_company_duplicate_phone_groups": int(
                ((phone_groups["rows"] > 1) & (phone_groups["companies"] > 1)).sum()
            ),
            "within_company_duplicate_phone_groups": int(
                (within_company > 1).sum()
            ),
            "ambiguous_slash_registration_dates": int(
                (leads["fecha_registro_parse_status"] == "AMBIGUOUS").sum()
            ),
        },
        "conversations": {
            "rows": len(conv_df),
            "unique_conversation_ids": conv_df["conversacion_id"].nunique(),
            "unique_lead_ids": conv_df["lead_id"].nunique(),
            "orphan_conversations": int(
                (~conv_df["lead_id"].isin(set(leads["lead_id"]))).sum()
            ),
            "leads_with_multiple_conversations": int(
                (conv_df["lead_id"].value_counts() > 1).sum()
            ),
            "avg_messages": round(conv_df["n_mensajes"].mean(), 2),
        },
        "catalog": {
            "rows": len(catalog),
            "brands": catalog["marca"].nunique(),
            "unique_skus": catalog["sku"].nunique(),
            "null_cells": int(catalog.isna().sum().sum()),
        },
        "advisors": {
            "rows": len(advisors),
            "active": int((advisors["activo"] == "SI").sum()),
            "inactive": int((advisors["activo"] == "NO").sum()),
            "active_daily_capacity": int(
                advisors.loc[
                    advisors["activo"] == "SI", "capacidad_diaria_leads"
                ].sum()
            ),
        },
        "historical": {
            "rows": len(history),
            "outcomes": history["desenlace"].value_counts().to_dict(),
            "close_rate_pct": round(history["closed"].mean() * 100, 2),
            "close_rate_contacted_only_pct": round(
                contacted["closed"].mean() * 100, 2
            ),
        },
    }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing the five assessment source files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("profile_summary.json"),
    )
    args = parser.parse_args()

    result = profile(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Profile written to {args.output}")


if __name__ == "__main__":
    main()
