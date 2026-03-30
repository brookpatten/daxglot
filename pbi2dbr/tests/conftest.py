"""pytest configuration and shared fixtures for pbi2dbr tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="class")
def _inject_fake_pbix(request, tmp_path_factory):
    """Create a real (empty) .pbix file and inject its path as ``request.cls.fake_pbix``.

    This allows PbixExtractor to pass its file-existence check while PBIXRay
    itself is mocked out via ``unittest.mock.patch``.
    """
    if request.cls is None:
        yield
        return

    tmp_dir = tmp_path_factory.mktemp("pbix_data")
    pbix = tmp_dir / "fake.pbix"
    pbix.write_bytes(b"")
    request.cls.fake_pbix = str(pbix)
    yield
