from discord_integration import _split_into_topics


SAMPLE_TEXT = """
DSS UPDATES :s:
The DSS has moved from LESATH to FORI PRIME :s::s:
:s: RUPTURE STRAIN
DSS BACK ONLINE
The Democracy Space Station (DSS) has returned from the orbital bombardment of LESATH.
Dispatch #3678
:s: GALACTIC WAR UPDATES :s:
NEW CAMPAIGNS :s:
DEFEND ERATA PRIME :shield::s:
Invasion Level 15!
Ends in 2 days
:s: Town NEW DA NANG
:s: Settlement PHAM'S SITE
:s: Town OLD CHEMLAND
:chess_pawn: Gambit: BORE ROCK
CYBERSTAN ORBITAL DEFENSES RE-ENGAGED
The orbital defence array on Cyberstan is back online. FTL travel to Cyberstan is no longer possible.
Dispatch #3679
""".strip()


def test_split_into_topics_identifies_sections():
    topics = _split_into_topics(SAMPLE_TEXT)

    assert any(topic.startswith("DSS UPDATES") for topic in topics)
    assert any("GALACTIC WAR UPDATES" in topic for topic in topics)
    assert any("CYBERSTAN ORBITAL DEFENSES" in topic for topic in topics)
    # Ensure topics are concise
    for topic in topics:
        assert "::" not in topic
