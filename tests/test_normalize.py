import pytest

from discord_integration import _normalize_combined_text


def test_normalize_combined_text_removes_tokens():
    raw = (
        ":s: GALACTIC WAR UPDATES :s:\n"
        "NEW CAMPAIGNS :s:\n"
        "DEFEND ERATA PRIME :shield::s:\n"
        "Invasion Level 15!\n"
        "Ends in 2 days\n"
        ":s: Town NEW DA NANG\n"
        ":s: Settlement PHAM'S SITE\n"
        ":s: Town OLD CHEMLAND\n"
        ":chess_pawn: Gambit: BORE ROCK"
    )

    normalized = _normalize_combined_text(raw)

    assert "GALACTIC WAR UPDATES" in normalized
    assert "DEFEND ERATA PRIME" in normalized
    assert ":s:" not in normalized
    assert "  " not in normalized
    assert "#" not in normalized
