from app.repositories.sqlalchemy import like


def test_plain_text_is_wrapped_for_a_contains_match() -> None:
    assert like.contains("budget") == "%budget%"


def test_wildcards_in_user_input_match_literally() -> None:
    assert like.contains("50%") == "%50\\%%"
    assert like.contains("a_b") == "%a\\_b%"


def test_the_escape_character_itself_is_escaped_first() -> None:
    # Escaping "\" after "%" would turn the escape we just added into a literal backslash.
    assert like.contains("c:\\100%") == "%c:\\\\100\\%%"
