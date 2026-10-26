from app.migrate import discover


def test_migrations_are_ordered_and_non_empty():
    migrations = discover()
    versions = [version for version, _ in migrations]
    assert versions == sorted(versions)
    assert versions[0] == "0001_baseline"
    assert all(sql.strip() for _, sql in migrations)