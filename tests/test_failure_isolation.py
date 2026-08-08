from series_lab.models import SeriesCandidate
from series_lab.services.search import search_providers


class Works:
    def __init__(self, name): self.name = name
    def search(self, query, limit=8): return [SeriesCandidate(self.name, self.name, self.name)]


class Fails:
    def search(self, query, limit=8): raise RuntimeError("temporarily down")


def test_one_provider_failure_does_not_fail_search():
    providers = {"FRED": Works("fred"), "Yahoo": Fails(), "BLS": Works("bls")}
    outcome = search_providers(providers, "copper", list(providers))
    assert {item.provider for item in outcome.results} == {"fred", "bls"}
    assert outcome.failures == {"Yahoo": "temporarily down"}
