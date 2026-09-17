import pytest

from reto_ia.llm.semantics import (
    enforce_customer_signal_evidence,
    normalize_money,
    parse_colombian_amount,
    reconcile_explicit_facts,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1.500.000", 1_500_000),
        ("1.500.000", 1_500_000),
        ("1,500,000", 1_500_000),
        ("2 millones", 2_000_000),
        ("1 palo", 1_000_000),
        ("6 palos", 6_000_000),
        ("2000 mil", 2_000_000),
        ("2000mil", 2_000_000),
        ("3000mil", 3_000_000),
        ("4900 mil", 4_900_000),
        ("1.5 millones", 1_500_000),
    ],
)
def test_parse_colombian_amount(text, expected):
    assert parse_colombian_amount(text) == expected
    assert normalize_money(text) == expected


def _payload():
    return {
        "modelo_interes": None,
        "presupuesto": None,
        "cuota_inicial": None,
        "forma_pago": "no_informa",
        "intencion": "indeterminada",
        "objecion_principal": None,
        "pidio_cita": False,
        "pidio_cotizacion": False,
        "evidencia": [],
    }


def test_reconcile_explicit_initial_and_payment_facts():
    result = reconcile_explicit_facts(
        _payload(),
        [{"emisor": "cliente", "texto": "Financiada, tengo 2000mil de inicial"}],
    )
    assert result["forma_pago"] == "credito"
    assert result["cuota_inicial"] == 2_000_000


def test_reconcile_cash_budget_does_not_create_downpayment():
    result = reconcile_explicit_facts(
        _payload(),
        [{"emisor": "cliente", "texto": "De contado, ya tengo la plata lista, 6 palos"}],
    )
    assert result["forma_pago"] == "contado"
    assert result["presupuesto"] == 6_000_000
    assert result["cuota_inicial"] is None


def test_reconcile_low_intent_quote_and_appointment_rules():
    result = reconcile_explicit_facts(
        _payload(),
        [
            {"emisor": "cliente", "texto": "Era por curiosidad nomás"},
            {"emisor": "asesor", "texto": "Le envío una cotización"},
            {"emisor": "cliente", "texto": "Gracias, quedo pendiente"},
        ],
    )
    assert result["intencion"] == "baja"
    assert result["pidio_cotizacion"] is False

    result = reconcile_explicit_facts(
        _payload(),
        [
            {"emisor": "asesor", "texto": "Puede visitarnos"},
            {"emisor": "cliente", "texto": "¿Mañana los visito?"},
        ],
    )
    assert result["pidio_cita"] is True


def test_reconcile_quote_acceptance_requires_sequence():
    result = reconcile_explicit_facts(
        _payload(),
        [
            {"emisor": "asesor", "texto": "Le puedo enviar la cotización"},
            {"emisor": "cliente", "texto": "Bueno, mándela"},
        ],
    )
    assert result["pidio_cotizacion"] is True


def test_advisor_financial_evidence_cannot_become_customer_downpayment():
    payload = {
        "cuota_inicial": 480_000,
        "presupuesto": None,
        "modelo_interes": None,
        "forma_pago": "credito",
        "intencion": "indeterminada",
        "objecion_principal": None,
        "pidio_cita": False,
        "pidio_cotizacion": False,
        "evidencia": [
            {
                "campo": "cuota_inicial",
                "fragmento": "la cuota queda en $480.000",
                "emisor": "asesor",
            }
        ],
    }
    assert enforce_customer_signal_evidence(payload)["cuota_inicial"] is None


def test_cash_amount_is_not_automatically_downpayment():
    payload = {
        "cuota_inicial": 6_000_000,
        "presupuesto": 6_000_000,
        "modelo_interes": None,
        "forma_pago": "contado",
        "intencion": "media",
        "objecion_principal": None,
        "pidio_cita": False,
        "pidio_cotizacion": False,
        "evidencia": [
            {"campo": "presupuesto", "fragmento": "De contado, 6 palos", "emisor": "cliente"}
        ],
    }
    result = enforce_customer_signal_evidence(payload)
    assert result["presupuesto"] == 6_000_000
    assert result["cuota_inicial"] is None


def test_vague_follow_up_does_not_become_quote_request():
    payload = {
        "cuota_inicial": None,
        "presupuesto": None,
        "modelo_interes": None,
        "forma_pago": "no_informa",
        "intencion": "baja",
        "objecion_principal": None,
        "pidio_cita": False,
        "pidio_cotizacion": True,
        "evidencia": [],
    }
    assert enforce_customer_signal_evidence(payload)["pidio_cotizacion"] is False
