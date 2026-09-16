from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process

# Conservative acceptance rule selected after inspecting the unique unresolved
# variants: require at least 90% ratio and 10 percentage points of separation.
FUZZY_SCORE_THRESHOLD = 0.90
FUZZY_MARGIN_THRESHOLD = 0.10


def normalize_model(value: str | None) -> str:
    if value is None:
        return ""
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", str(value).strip().lower())
        if not unicodedata.combining(char)
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_catalog(input_dir: Path) -> list[dict[str, str]]:
    with (input_dir / "catalogo_motos.csv").open(
        encoding="utf-8", newline=""
    ) as file:
        rows = list(csv.DictReader(file))
    return [
        {
            "sku": row["sku"],
            "modelo_canonico": f"{row['marca']} {row['linea']}",
            "modelo_normalizado": normalize_model(f"{row['marca']} {row['linea']}"),
        }
        for row in rows
    ]


def load_lead_models(input_dir: Path) -> set[str]:
    with (input_dir / "leads.csv").open(encoding="utf-8", newline="") as file:
        return {
            normalize_model(row["modelo_interes_texto"])
            for row in csv.DictReader(file)
            if normalize_model(row["modelo_interes_texto"])
        }


def build_aliases(models: set[str], catalog: list[dict[str, str]]) -> dict[str, str]:
    by_normalized = {row["modelo_normalizado"]: row["sku"] for row in catalog}
    by_line = {}
    for row in catalog:
        line = normalize_model(row["modelo_canonico"].split(" ", 1)[1])
        by_line.setdefault(line, []).append(row["sku"])

    aliases: dict[str, str] = {}
    for model in sorted(models):
        candidates = {
            model,
            re.sub(r"\s+2026$", "", model),
        }
        for candidate in candidates:
            if candidate in by_normalized:
                aliases[model] = by_normalized[candidate]
                break

        if model in aliases:
            continue

        # A line-only or brand-plus-unique-prefix request is safe only when
        # exactly one catalog reference can satisfy it.
        line_matches = [
            sku for line, skus in by_line.items() if line == model for sku in skus
        ]
        if len(line_matches) == 1:
            aliases[model] = line_matches[0]
            continue

        prefix_matches = [
            row["sku"]
            for row in catalog
            if row["modelo_normalizado"].startswith(model + " ")
        ]
        if len(prefix_matches) == 1:
            aliases[model] = prefix_matches[0]

    return aliases


def build_fuzzy_rows(
    models: set[str], catalog: list[dict[str, str]], aliases: dict[str, str]
) -> list[dict[str, str]]:
    choices = [row["modelo_normalizado"] for row in catalog]
    brands = {normalize_model(row["modelo_canonico"].split(" ", 1)[0]) for row in catalog}
    rows = []
    for model in sorted(models - set(aliases)):
        matches = process.extract(model, choices, scorer=fuzz.ratio, limit=2)
        first, second = matches[0], matches[1]
        top_1, top_1_score = first[0], first[1] / 100
        top_2, top_2_score = second[0], second[1] / 100
        margin = top_1_score - top_2_score
        prefix_count = sum(choice.startswith(model + " ") for choice in choices)
        if model in brands or prefix_count > 1:
            decision = "AMBIGUOUS"
        elif top_1_score >= FUZZY_SCORE_THRESHOLD and margin >= FUZZY_MARGIN_THRESHOLD:
            decision = "MATCHED"
        else:
            decision = "REVIEW"
        rows.append({
            "modelo_interes_normalizado": model,
            "top_1": top_1,
            "top_1_score": f"{top_1_score:.4f}",
            "top_2": top_2,
            "top_2_score": f"{top_2_score:.4f}",
            "margin": f"{margin:.4f}",
            "decision": decision,
            "sku": next(row["sku"] for row in catalog if row["modelo_normalizado"] == top_1),
        })
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic catalog matching seeds.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--seed-dir", type=Path, default=Path("dbt/seeds"))
    args = parser.parse_args()

    catalog = load_catalog(args.input_dir)
    models = load_lead_models(args.input_dir)
    aliases = build_aliases(models, catalog)
    fuzzy_rows = build_fuzzy_rows(models, catalog, aliases)
    alias_rows = [
        {"alias_normalizado": alias, "sku": sku}
        for alias, sku in sorted(aliases.items())
        if alias not in {row["modelo_normalizado"] for row in catalog}
    ]
    write_csv(
        args.seed_dir / "model_aliases.csv",
        ["alias_normalizado", "sku"],
        alias_rows,
    )
    write_csv(
        args.seed_dir / "model_fuzzy_matches.csv",
        [
            "modelo_interes_normalizado", "top_1", "top_1_score", "top_2",
            "top_2_score", "margin", "decision", "sku",
        ],
        fuzzy_rows,
    )
    print(f"aliases={len(alias_rows)} fuzzy_candidates={len(fuzzy_rows)}")
    print({
        decision: sum(row["decision"] == decision for row in fuzzy_rows)
        for decision in {row["decision"] for row in fuzzy_rows}
    })


if __name__ == "__main__":
    main()
