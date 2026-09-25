"""Tests for data-source contracts established before source selection."""

from cybersecurity_advisor.ingestion.schemas import SourceDefinition, SourceManifest


def test_source_is_disabled_until_reviewed() -> None:
    source = SourceDefinition(
        source_id="candidate-source",
        name="Candidate source",
        organization="Example organization",
        base_url="https://example.com/security",
        languages=["th", "en"],
        source_type="government",
    )

    assert source.enabled is False


def test_empty_manifest_is_valid_before_source_selection() -> None:
    manifest = SourceManifest(manifest_version="1.0")

    assert manifest.reviewed_at is None
    assert manifest.reviewed_by == []
    assert manifest.sources == []
