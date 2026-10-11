"""Smoke test — verify the package is importable."""


def test_import():
    import opensynth_ne

    assert hasattr(opensynth_ne, "generate_day")
    assert hasattr(opensynth_ne, "generate")
