"""Small deterministic guards for customer-declared commercial signals."""

import re
from collections.abc import Iterable, Mapping
from typing import Any

_AMOUNT = re.compile(r"(?P<number>\d+(?:[.,]\d+)*)\s*(?P<suffix>millones?|mm?|palos?|mil)?", re.I)
_MONEY_CONTEXT = re.compile(
    r"(?:\$|cop|pesos?|millones?|palos?|mil|presupuesto|plata|dinero|inicial|entrada|enganche|cuota)",
    re.I,
)


def _parse_number(value: str) -> float:
    groups = value.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", groups):
        return float(groups.replace(".", "").replace(",", ""))
    return float(groups.replace(",", "."))


def parse_colombian_amount(text: str) -> float | None:
    """Parse a monetary expression only when its surrounding text is monetary."""

    if not _MONEY_CONTEXT.search(text) and not re.fullmatch(
        r"\s*\$?\d{1,3}(?:[.,]\d{3})+\s*", text
    ):
        return None
    match = _AMOUNT.search(text)
    if not match:
        return None
    amount = _parse_number(match.group("number"))
    suffix = (match.group("suffix") or "").lower()
    if suffix.startswith(("millon", "palo")):
        amount *= 1_000_000
    elif suffix.startswith(("mil", "m")):
        amount *= 1_000
    return amount


normalize_money = parse_colombian_amount


def _client_messages(messages: Iterable[Mapping[str, Any]]) -> list[tuple[int, str]]:
    return [
        (index, str(message.get("texto", "")))
        for index, message in enumerate(messages)
        if str(message.get("emisor", "")).casefold() == "cliente"
        and isinstance(message.get("texto"), str)
        and message.get("texto", "").strip()
    ]


def _evidence(payload: dict[str, Any], field: str, fragment: str) -> None:
    if not fragment or not fragment.strip():
        return
    evidence = payload.setdefault("evidencia", [])
    item = {"campo": field, "fragmento": fragment[:240], "emisor": "cliente"}
    if item not in evidence and len(evidence) < 5:
        evidence.append(item)


_INITIAL = re.compile(
    r"(?P<amount>\$?\s*\d+(?:[.,]\d+)*\s*(?:millones?|mil|palos?|mm?)?)"
    r"\s*(?:de|para(?:\s+la)?)?\s*(?:cuota\s+)?(?:inicial|entrada)\b",
    re.I,
)
_CONTADO = re.compile(r"\b(?:de|al)\s+contado\b|\bcontado\b", re.I)
_CREDITO = re.compile(r"\b(?:a\s+cr[eé]dito|financiad[ao]|financiar(?:la|lo)?)\b", re.I)
_LOW_INTENT = re.compile(
    r"\b(?:era\s+por\s+curiosidad|solo\s+estaba\s+mirando|solo\s+estaba\s+averiguando\s+por\s+curiosidad)\b",
    re.I,
)
_STRONG_INTENT = re.compile(
    r"\b(?:voy\b|ya\s+voy|quiero\s+comprar|sep[aá]rem|agend|puedo\s+pasar)\b",
    re.I,
)
_QUOTE_REQUEST = re.compile(
    r"\b(?:cotiz|cu[aá]nto\s+me\s+queda|en\s+cu[aá]nto\s+queda|simul|valor|cuotas?)\b",
    re.I,
)
_QUOTE_ACCEPTANCE = re.compile(r"\b(?:m[aá]ndela|env[ií]emela|s[ií],?\s+env[ií]e)", re.I)
_ADVISOR_QUOTE_OFFER = re.compile(r"\b(?:cotiz|simul)\w*", re.I)
_APPOINTMENT = re.compile(
    r"\b(?:voy\s+(?:esta|hoy|ma[ñn]ana)|ya\s+voy\s+en\s+camino|visito|puedo\s+pasar|agend)",
    re.I,
)


def reconcile_explicit_facts(
    payload: dict[str, Any], messages: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Apply only explicit, client-authored facts to a structured extraction."""

    source_messages = list(messages)
    client_messages = _client_messages(source_messages)
    if not client_messages:
        return payload

    latest_payment: tuple[int, str] | None = None
    latest_initial: tuple[int, float, str] | None = None
    latest_budget: tuple[int, float, str] | None = None
    low_intent: tuple[int, str] | None = None
    strong_intent_after = False
    quote_acceptance: tuple[int, str] | None = None
    advisor_quote_offers = {
        index
        for index, message in enumerate(source_messages)
        if str(message.get("emisor", "")).casefold() == "asesor"
        and _ADVISOR_QUOTE_OFFER.search(str(message.get("texto", "")))
    }

    for index, text in client_messages:
        initial = _INITIAL.search(text)
        if initial:
            amount = parse_colombian_amount(initial.group("amount"))
            if amount is not None:
                latest_initial = (index, amount, text)

        if _CONTADO.search(text) and not ("?" in text and _CREDITO.search(text)):
            latest_payment = (index, "contado")
        elif _CREDITO.search(text) and not ("?" in text and _CONTADO.search(text)):
            latest_payment = (index, "credito")

        if _LOW_INTENT.search(text):
            low_intent = (index, text)
        if _STRONG_INTENT.search(text):
            strong_intent_after = True

        if _QUOTE_REQUEST.search(text):
            quote_acceptance = (index, text)
        elif _QUOTE_ACCEPTANCE.search(text) and any(
            offer_index < index for offer_index in advisor_quote_offers
        ):
            quote_acceptance = (index, text)

        if parse_colombian_amount(text) is not None and not initial:
            latest_budget = (index, parse_colombian_amount(text), text)  # type: ignore[arg-type]

    if latest_payment:
        payload["forma_pago"] = latest_payment[1]
        payment_text = next(text for index, text in client_messages if index == latest_payment[0])
        _evidence(payload, "forma_pago", payment_text)

    if latest_initial:
        payload["cuota_inicial"] = latest_initial[1]
        _evidence(payload, "cuota_inicial", latest_initial[2])
    elif latest_payment and latest_payment[1] == "contado":
        payload["cuota_inicial"] = None
        if latest_budget:
            payload["presupuesto"] = latest_budget[1]
            _evidence(payload, "presupuesto", latest_budget[2])

    if low_intent and not strong_intent_after:
        payload["intencion"] = "baja"
        _evidence(payload, "intencion", low_intent[1])

    if quote_acceptance:
        payload["pidio_cotizacion"] = True
        _evidence(payload, "pidio_cotizacion", quote_acceptance[1])

    if any(_APPOINTMENT.search(text) for _, text in client_messages):
        payload["pidio_cita"] = True
        appointment_text = next(text for _, text in client_messages if _APPOINTMENT.search(text))
        _evidence(payload, "pidio_cita", appointment_text)

    return payload


def _client_evidence(payload: Mapping[str, Any], field: str) -> list[str]:
    evidence = payload.get("evidencia")
    if not isinstance(evidence, Iterable) or isinstance(evidence, (str, bytes)):
        return []
    return [
        item["fragmento"]
        for item in evidence
        if isinstance(item, Mapping)
        and item.get("campo") == field
        and str(item.get("emisor", "")).casefold() == "cliente"
        and isinstance(item.get("fragmento"), str)
    ]


def enforce_customer_signal_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Prevent advisor-only evidence from becoming customer attributes.

    This is intentionally conservative: an unsupported value is cleared rather
    than inferred from another field or from the advisor's message.
    """

    for field in ("modelo_interes", "presupuesto", "cuota_inicial"):
        fragments = _client_evidence(payload, field)
        if payload.get(field) is not None and not fragments:
            payload[field] = None
        elif fragments and payload.get(field) is not None:
            parsed = next((parse_colombian_amount(fragment) for fragment in fragments), None)
            if parsed is not None:
                payload[field] = parsed

    if payload.get("forma_pago") in ("credito", "contado") and not _client_evidence(
        payload, "forma_pago"
    ):
        payload["forma_pago"] = "no_informa"

    for field in ("pidio_cita", "pidio_cotizacion"):
        if payload.get(field) is True and not _client_evidence(payload, field):
            payload[field] = False

    return payload
