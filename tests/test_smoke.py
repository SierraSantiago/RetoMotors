from pathlib import Path


def test_assessment_inputs_exist():
    expected = {
        "leads.csv",
        "conversaciones.json",
        "catalogo_motos.csv",
        "asesores.csv",
        "historico_cierres.csv",
    }
    data_dir = Path("data/input")
    assert expected.issubset({p.name for p in data_dir.iterdir() if p.is_file()})
