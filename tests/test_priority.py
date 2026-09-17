from datetime import UTC, datetime

from reto_ia.priority.assignment import add_ranks, assign_rows
from reto_ia.priority.scoring import (
    availability_component,
    conversation_component,
    percentile_map,
    score_rows,
    sla_component,
)


def base_row(**overrides):
    row = {
        "raw_row_id": "r1",
        "fecha_registro": datetime(2026, 9, 15).date(),
        "has_conversation": True,
        "conversation_intencion": "alta",
        "conversation_pidio_cita": True,
        "conversation_pidio_cotizacion": True,
        "conversation_cuota_inicial": 100,
        "conversation_forma_pago": "credito",
        "is_available_at_store": True,
        "propensity_score": 0.5,
        "empresa_id": "E1",
        "punto_venta_id": "P1",
    }
    return {**row, **overrides}


def test_maximum_conversation_component_and_zero_initial():
    component, _ = conversation_component(base_row())
    assert component == 45
    zero, _ = conversation_component(base_row(conversation_cuota_inicial=0))
    assert zero == 38
    cash, _ = conversation_component(
        base_row(conversation_forma_pago="contado")
    )
    assert cash == 38


def test_sla_boundaries_and_availability():
    assert sla_component(3.99)[0] == 0
    assert sla_component(4)[0] == 5
    assert sla_component(12)[0] == 10
    assert sla_component(24)[0] == 20
    assert sla_component(48)[0] == 30
    assert availability_component(True)[0] == 20
    assert availability_component(False)[0] == 0
    assert availability_component(None)[0] == 8


def test_percentiles_are_deterministic_with_ties():
    rows = [
        base_row(raw_row_id="b"),
        base_row(raw_row_id="a"),
        base_row(raw_row_id="c", propensity_score=0.9),
    ]
    assert percentile_map(rows) == {"a": 0.0, "b": 0.5, "c": 1.0}


def test_assignment_respects_capacity_company_store_and_determinism():
    rows = score_rows(
        [base_row(raw_row_id="a"), base_row(raw_row_id="b", empresa_id="E2")],
        datetime(2026, 9, 17, tzinfo=UTC),
    )
    assigned = add_ranks(assign_rows(rows, [
        {
            "asesor_id": "z", "empresa_id": "E1", "punto_venta_id": "P1",
            "activo": True, "capacidad_diaria_leads": 1,
        },
    ]))
    by_id = {row["raw_row_id"]: row for row in assigned}
    assert by_id["a"]["assignment_status"] == "ASSIGNED"
    assert by_id["b"]["assignment_status"] == "NO_ELIGIBLE_ADVISOR"
    assert {by_id["a"]["global_priority_rank"], by_id["b"]["global_priority_rank"]} == {1, 2}


def test_score_range():
    row = score_rows([base_row()], datetime(2026, 9, 17, tzinfo=UTC))[0]
    assert 0 <= row["priority_score"] <= 100
