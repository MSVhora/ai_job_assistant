from collections.abc import AsyncIterator

import pytest

from app.adapters.evidence_sources import registry
from app.adapters.evidence_sources.base import (
    EvidenceSource,
    EvidenceSourceConfigError,
    EvidenceSourceError,
    RawEvidence,
)
from app.schemas.evidence import (
    EvidenceItemData,
    ScopeCandidate,
    ScopeState,
    SourceIdentity,
    SyncPage,
)


class FakeEvidenceSource:
    name = "fake"

    def is_configured(self) -> bool:
        return True

    async def identify(self) -> SourceIdentity:
        return SourceIdentity(login="ada")

    async def list_scopes(self) -> list[ScopeCandidate]:
        return [ScopeCandidate(ref="ada/repo")]

    async def sync_scope(self, scope: ScopeState) -> AsyncIterator[SyncPage]:
        yield SyncPage(items=[], next_cursor=None)

    def normalize(self, raw: RawEvidence) -> EvidenceItemData:
        return EvidenceItemData(kind="note", external_id=str(raw["id"]), body="b")


def test_registry_is_empty_until_a_connector_registers() -> None:
    assert registry.registered_sources() == ()


def test_get_source_unknown_name_raises_typed_error() -> None:
    with pytest.raises(EvidenceSourceConfigError, match="unknown evidence source"):
        registry.get_source("nope")


def test_config_error_is_an_evidence_source_error() -> None:
    assert issubclass(EvidenceSourceConfigError, EvidenceSourceError)


async def test_fake_source_satisfies_protocol_and_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeEvidenceSource()
    monkeypatch.setitem(registry._REGISTRY, fake.name, fake)

    source: EvidenceSource = registry.get_source("fake")

    assert registry.registered_sources() == (fake,)
    assert (await source.identify()).login == "ada"
    pages = [page async for page in source.sync_scope(ScopeState(ref="ada/repo"))]
    assert pages == [SyncPage()]
    assert source.normalize({"id": 7}).external_id == "7"
