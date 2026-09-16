from reto_ia.ingestion.readers import REQUIRED_FILES


def test_required_sources_are_declared():
    assert set(REQUIRED_FILES) == {
        "leads.csv",
        "conversaciones.json",
        "catalogo_motos.csv",
        "asesores.csv",
        "historico_cierres.csv",
    }
