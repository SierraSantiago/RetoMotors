import csv
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CSV_CONTRACTS = {
    "leads.csv": [
        "lead_id", "fecha_registro", "canal", "empresa_id", "punto_venta_id",
        "nombre_cliente", "telefono", "email", "ciudad", "modelo_interes_texto",
        "estado_gestion", "fecha_primer_contacto", "campania",
    ],
    "catalogo_motos.csv": [
        "sku", "marca", "linea", "cilindraje", "segmento", "precio_lista",
        "puntos_venta_disponibles", "unidades_disponibles",
    ],
    "asesores.csv": [
        "asesor_id", "nombre", "punto_venta_id", "empresa_id",
        "capacidad_diaria_leads", "activo", "fecha_ingreso",
    ],
    "historico_cierres.csv": [
        "lead_id", "fecha_registro", "canal", "empresa_id", "punto_venta_id",
        "modelo_cotizado", "precio_lista", "horas_al_primer_contacto",
        "numero_contactos", "manifesto_cuota_inicial", "forma_pago_declarada",
        "pidio_cita", "desenlace",
    ],
}
REQUIRED_FILES = (*CSV_CONTRACTS.keys(), "conversaciones.json")


@dataclass(frozen=True)
class SourceRow:
    source_row_number: int
    values: dict[str, Any]
    raw_payload: dict[str, Any]


def _open_text(path: Path):
    return path.open("r", encoding="utf-8-sig", newline="")


def validate_csv_contract(path: Path, required_columns: list[str]) -> None:
    with _open_text(path) as source:
        reader = csv.reader(source)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path.name}: archivo CSV vacío") from exc
    missing = [column for column in required_columns if column not in header]
    if missing:
        raise ValueError(f"{path.name}: faltan columnas requeridas: {', '.join(missing)}")


def read_csv(path: Path, required_columns: list[str]) -> Iterator[SourceRow]:
    validate_csv_contract(path, required_columns)
    with _open_text(path) as source:
        reader = csv.DictReader(source)
        for row_number, row in enumerate(reader, start=2):
            payload = dict(row)
            yield SourceRow(row_number, {key: row.get(key) for key in required_columns}, payload)


def validate_conversations_contract(path: Path) -> None:
    try:
        with path.open("r", encoding="utf-8-sig") as source:
            document = json.load(source)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}: JSON inválido: {exc.msg}") from exc
    if not isinstance(document, list):
        raise ValueError(f"{path.name}: debe contener un array de objetos")
    required = {"conversacion_id", "lead_id", "canal", "fecha_inicio", "mensajes"}
    for index, item in enumerate(document, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{path.name}: el elemento {index} no es un objeto")
        missing = required - item.keys()
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise ValueError(f"{path.name}: elemento {index} sin campos: {missing_fields}")
        if not isinstance(item["mensajes"], list):
            raise ValueError(f"{path.name}: mensajes del elemento {index} debe ser una lista")


def read_conversations(path: Path) -> Iterator[SourceRow]:
    validate_conversations_contract(path)
    with path.open("r", encoding="utf-8-sig") as source:
        document = json.load(source)
    for row_number, item in enumerate(document, start=1):
        yield SourceRow(row_number, {
            "conversacion_id": item["conversacion_id"],
            "lead_id": item["lead_id"],
            "canal": item["canal"],
            "fecha_inicio": item["fecha_inicio"],
            "mensajes": item["mensajes"],
        }, item)
