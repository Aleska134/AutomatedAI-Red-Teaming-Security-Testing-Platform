import pytest

from app.database import _database_url


@pytest.mark.parametrize(
    "url",
    ["postgres://u:p@host/db", "postgresql://u:p@host/db"],
)
def test_postgres_urls_use_psycopg2_driver(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    assert _database_url() == "postgresql+psycopg2://u:p@host/db"


def test_sqlite_url_is_unchanged(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    assert _database_url() == "sqlite:///x.db"
