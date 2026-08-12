import pytest

from tennis_entry_watch.normalize import stable_player_id


def test_fallback_player_id_normalizes_diacritics_and_punctuation():
    assert stable_player_id("João Fonseca") == "joao-fonseca"
    assert stable_player_id("Fonseca, Joao") == "fonseca-joao"


def test_fallback_player_id_rejects_empty_result():
    with pytest.raises(ValueError):
        stable_player_id("---")
