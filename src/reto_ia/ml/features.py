from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

NUMERIC_FEATURES = ["precio_lista"]
CATEGORICAL_FEATURES = ["empresa_id", "punto_venta_id", "canal_normalizado", "modelo_feature"]
BOOLEAN_FEATURES = ["manifesto_cuota_inicial", "pidio_cita"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES + BOOLEAN_FEATURES
EXCLUDED_FEATURES = {
    "outcome": "target/resultado comercial",
    "fecha_cierre": "post-treatment/outcome; no existe como feature de entrada",
    "numero_contactos": "post-treatment",
    "horas_al_primer_contacto": "operacional posterior a la priorización inicial",
    "lead_id": "identificador, no predictor",
    "raw_row_id": "identificador, no predictor",
    "conversation_intencion": "no existe históricamente de forma comparable",
    "conversation_pidio_cotizacion": "no existe históricamente de forma comparable",
    "conversation_objecion_principal": "no existe históricamente de forma comparable",
}

LEAKAGE_AUDIT = [
    ("fecha_registro", "TIMESTAMP", False, "solo split temporal; no predictor"),
    ("empresa_id", "ELIGIBLE", True, "contexto disponible al ingreso"),
    ("punto_venta_id", "ELIGIBLE", True, "contexto disponible al ingreso"),
    ("canal_normalizado", "ELIGIBLE", True, "canal de entrada"),
    (
        "modelo_cotizado_normalizado/modelo_canonico",
        "ELIGIBLE",
        True,
        "modelo disponible al ingreso",
    ),
    ("precio_lista", "ELIGIBLE", True, "precio disponible al ingreso"),
    ("manifesto_cuota_inicial", "ELIGIBLE", True, "declaración disponible al ingreso"),
    ("pidio_cita", "ELIGIBLE", True, "señal disponible en el registro"),
    ("desenlace_normalizado/is_closed", "TARGET/OUTCOME", False, "resultado usado como target"),
    ("lead_id/raw_row_id", "IDENTIFIER", False, "identificadores sin valor predictivo"),
    ("numero_contactos", "POST_TREATMENT", False, "resultado de gestión posterior"),
    ("horas_al_primer_contacto", "POST_TREATMENT", False, "operación posterior a priorización"),
    (
        "forma_pago_declarada",
        "UNAVAILABLE_AT_SERVING",
        False,
        "sin fuente equivalente segura en serving",
    ),
    (
        "conversation_intencion/pidio_cotizacion/objecion",
        "UNAVAILABLE_AT_TRAIN",
        False,
        "sin equivalente histórico comparable",
    ),
]


@dataclass(frozen=True)
class FeatureContract:
    numeric: tuple[str, ...] = tuple(NUMERIC_FEATURES)
    categorical: tuple[str, ...] = tuple(CATEGORICAL_FEATURES)
    boolean: tuple[str, ...] = tuple(BOOLEAN_FEATURES)

    @property
    def columns(self) -> list[str]:
        return [*self.numeric, *self.categorical, *self.boolean]

    def validate(self, frame: pd.DataFrame) -> None:
        missing = [column for column in self.columns if column not in frame.columns]
        if missing:
            raise ValueError(f"Feature contract missing columns: {missing}")


CONTRACT = FeatureContract()


def prepare_features(frame: pd.DataFrame) -> pd.DataFrame:
    CONTRACT.validate(frame)
    result = frame.loc[:, CONTRACT.columns].copy()
    for column in CONTRACT.boolean:
        result[column] = result[column].astype("boolean")
    return result


def training_query() -> str:
    return """
        select
            raw_row_id,
            lead_id,
            fecha_registro,
            empresa_id,
            punto_venta_id,
            canal_normalizado,
            modelo_cotizado_normalizado as modelo_feature,
            precio_lista,
            manifesto_cuota_inicial,
            pidio_cita,
            desenlace_normalizado
        from staging.stg_historico_cierres
        where desenlace_normalizado in ('cerrado', 'perdido')
        order by fecha_registro, raw_row_id
    """


def serving_query() -> str:
    return """
        select
            raw_row_id,
            lead_id,
            fecha_registro,
            empresa_id,
            punto_venta_id,
            canal_normalizado,
            coalesce(modelo_canonico, modelo_interes_normalizado) as modelo_feature,
            precio_lista,
            null::boolean as manifesto_cuota_inicial,
            conversation_pidio_cita as pidio_cita
        from marts.mart_leads_ai_enriched
        order by raw_row_id
    """
