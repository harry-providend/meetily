from app.services.implementations.match_context_extractor import MatchContextExtractor


def test_window_is_trimmed_and_marked_on_both_sides() -> None:
    extractor = MatchContextExtractor(window=5)
    result = extractor.extract("aaaaaaaaaaNEEDLEbbbbbbbbbb", "needle")
    assert result == "...aaaaaNEEDLEbbbbb..."


def test_no_ellipsis_when_the_window_covers_the_whole_segment() -> None:
    extractor = MatchContextExtractor(window=100)
    assert extractor.extract("just the needle", "needle") == "just the needle"


def test_a_segment_without_the_query_falls_back_to_its_opening() -> None:
    extractor = MatchContextExtractor(fallback_length=4)
    assert extractor.extract("abcdefgh", "zzz") == "abcd"


def test_multibyte_characters_do_not_split() -> None:
    # The Rust helper this replaces slices &str by byte offset and panics here.
    transcript = "日本語のテキストです NEEDLE 続きの日本語テキスト"
    result = MatchContextExtractor(window=3).extract(transcript, "needle")
    assert result == "...です NEEDLE 続き..."
