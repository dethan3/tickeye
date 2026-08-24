from pathlib import Path

from tickeye.config import Settings


def test_settings_accept_explicit_local_overrides(tmp_path: Path) -> None:
    database_path = tmp_path / "tickeye.db"

    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{database_path}",
        frontend_dist_dir=tmp_path / "dist",
        cors_origins=("http://localhost:5173",),
    )

    assert settings.environment == "test"
    assert settings.database_url.endswith("tickeye.db")
    assert settings.frontend_dist_dir == tmp_path / "dist"
