import re
from pathlib import Path
import xml.etree.ElementTree as ET

FIXTURES = [
    """<speak><voice name='cast.alice'><prosody rate='95%'>Hello clause.</prosody></voice><break time='300ms'/><phoneme alphabet='ipa' ph='oʊboʊboʊ'>OBOBO</phoneme></speak>""",
]


def test_ssml_fixtures_are_valid_xml_and_policy_compliant():
    for ssml in FIXTURES:
        root = ET.fromstring(ssml)
        assert root.tag == "speak"
        for prosody in root.iter("prosody"):
            rate = prosody.attrib.get("rate", "100%")
            if rate.endswith("%"):
                numeric = int(rate[:-1])
                assert 50 <= numeric <= 160
            pitch = prosody.attrib.get("pitch")
            if pitch and pitch.endswith("%"):
                assert 75 <= int(pitch[:-1]) <= 125
        for clause in re.split(r"[.;!?]", "".join(root.itertext())):
            assert clause.count("<prosody") <= 1
