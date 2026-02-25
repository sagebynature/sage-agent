"""Shared test fixtures for Sage."""

import pytest


@pytest.fixture(autouse=True)
def _no_apollo_logging_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent apollo_logging.init() from reconfiguring root logging during tests.

    When CLI tests invoke commands, apollo_logging.init("logging.conf") would
    call logging.config.fileConfig() which sets propagate=0 on the sage
    logger, breaking pytest's caplog fixture for subsequent tests.
    """
    import apollo_logging  # type: ignore

    monkeypatch.setattr(apollo_logging, "init", lambda *args, **kwargs: None)
