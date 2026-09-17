from __future__ import annotations

from typing import Any


def assign_rows(rows: list[dict[str, Any]], advisors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state = {
        str(advisor["asesor_id"]): {"advisor": advisor, "assigned": 0}
        for advisor in advisors
        if advisor.get("activo") is True
    }
    output = []
    for row in rows:
        eligible = [
            item for item in state.values()
            if item["advisor"].get("empresa_id") == row.get("empresa_id")
            and item["advisor"].get("punto_venta_id") == row.get("punto_venta_id")
        ]
        available = [
            item for item in eligible
            if item["advisor"].get("capacidad_diaria_leads") is not None
            and item["assigned"] < item["advisor"]["capacidad_diaria_leads"]
        ]
        if available:
            selected = min(
                available,
                key=lambda item: (
                    item["assigned"] / item["advisor"]["capacidad_diaria_leads"],
                    item["assigned"],
                    str(item["advisor"]["asesor_id"]),
                ),
            )
            selected["assigned"] += 1
            advisor_id = selected["advisor"]["asesor_id"]
            status = "ASSIGNED"
        else:
            advisor_id = None
            status = "UNASSIGNED_CAPACITY" if eligible else "NO_ELIGIBLE_ADVISOR"
        output.append({**row, "advisor_id": advisor_id, "assignment_status": status})
    return output


def add_ranks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -row["priority_score"], row.get("fecha_registro") is None,
            row.get("fecha_registro"), str(row["raw_row_id"]),
        )
    global_order = sorted(rows, key=sort_key)
    global_ranks = {str(row["raw_row_id"]): rank for rank, row in enumerate(global_order, 1)}
    store_groups: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in rows:
        store_groups.setdefault((row.get("empresa_id"), row.get("punto_venta_id")), []).append(row)
    store_ranks = {}
    for group in store_groups.values():
        ordered = sorted(group, key=sort_key)
        for rank, row in enumerate(ordered, 1):
            store_ranks[str(row["raw_row_id"])] = rank
    return [
        {
            **row,
            "global_priority_rank": global_ranks[str(row["raw_row_id"])],
            "store_priority_rank": store_ranks[str(row["raw_row_id"])],
        }
        for row in rows
    ]
