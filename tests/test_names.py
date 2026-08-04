from lesgeefplanner.domain.names import display_names, is_exact, stel_voor
from lesgeefplanner.model import Lesgever


def test_jan_matcht_niet_exact_met_jen():
    """Regressietest: de oude code accepteerde Levenshtein < 3 stilzwijgend, waardoor 'Jan'
    aan 'Jen' werd gekoppeld. Dat mag hier niet als 'exact' gelden."""
    lesgevers = [Lesgever(naam="Jen Bakker")]
    voorstellen = stel_voor("Jan", lesgevers)
    assert not is_exact(voorstellen[0][1])


def test_exacte_volledige_naam():
    lesgevers = [Lesgever(naam="Anne de Vries"), Lesgever(naam="Bob")]
    voorstellen = stel_voor("Anne de Vries", lesgevers)
    assert voorstellen[0][0].naam == "Anne de Vries"
    assert is_exact(voorstellen[0][1])


def test_exacte_unieke_voornaam():
    lesgevers = [Lesgever(naam="Anne de Vries"), Lesgever(naam="Bob Jansen")]
    voorstellen = stel_voor("Anne", lesgevers)
    assert voorstellen[0][0].naam == "Anne de Vries"
    assert is_exact(voorstellen[0][1])


def test_voorstellen_gesorteerd_hoog_naar_laag():
    lesgevers = [Lesgever(naam="Anne"), Lesgever(naam="Anna"), Lesgever(naam="Zeb")]
    voorstellen = stel_voor("Anne", lesgevers)
    scores = [score for _, score in voorstellen]
    assert scores == sorted(scores, reverse=True)
    assert voorstellen[0][0].naam == "Anne"


def test_display_names_unieke_voornaam():
    a = Lesgever(naam="Anne de Vries")
    b = Lesgever(naam="Bob Jansen")
    namen = display_names([a, b])
    assert namen[a.id] == "Anne"
    assert namen[b.id] == "Bob"


def test_display_names_dubbele_voornaam_toont_volledige_naam():
    a = Lesgever(naam="Anne de Vries")
    b = Lesgever(naam="Anne Bakker")
    namen = display_names([a, b])
    assert namen[a.id] == "Anne de Vries"
    assert namen[b.id] == "Anne Bakker"
