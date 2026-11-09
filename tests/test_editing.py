from career_job_manager.editing import InlineBuffer


def test_inline_buffer_inserts_and_moves_cursor():
    editor = InlineBuffer.from_value("HSBC")
    assert editor.cursor == 4
    editor.move_left()
    editor.insert("X")
    assert editor.value == "HSBX C".replace(" ", "")
    assert editor.cursor == 4
    editor.move_home()
    editor.insert("A")
    assert editor.value == "AHSBXC"


def test_inline_buffer_backspace_delete_and_bounds():
    editor = InlineBuffer.from_value("abc")
    editor.move_left()
    editor.backspace()
    assert editor.value == "ac"
    assert editor.cursor == 1
    editor.delete()
    assert editor.value == "a"
    editor.move_left()
    editor.move_left()
    editor.backspace()
    assert editor.value == "a"
    assert editor.cursor == 0


def test_inline_buffer_renders_cursor_in_place():
    editor = InlineBuffer.from_value("Sep 25")
    editor.move_left()
    assert editor.render() == "Sep 2│5"


def test_paste_normalization_preserves_description_lines_but_flattens_single_line_fields():
    from career_job_manager.editing import normalize_pasted_text

    pasted = "  first\r\nsecond\tthird  "
    assert normalize_pasted_text(pasted, multiline=False) == "first second third"
    assert normalize_pasted_text(pasted, multiline=True) == "  first\nsecond    third  "


def test_right_stops_at_end():
    editor = InlineBuffer.from_value("ab\n中")
    editor.move_left()
    editor.move_right()
    assert editor.cursor == 4
    editor.move_right()
    assert editor.cursor == 4
    editor.move_right()
    assert editor.cursor == 4
    assert editor.value == "ab\n中"


def test_right_on_empty_text_and_selection():
    editor = InlineBuffer.from_value("")
    editor.move_right()
    assert editor.cursor == 0
    editor.insert("abc")
    editor.select_all()
    editor.move_right()
    assert not editor.all_selected
    assert editor.cursor == 3
    editor.move_right()
    assert editor.cursor == 3
    assert editor.value == "abc"



def test_select_all_and_replace_a_long_portal_in_one_paste():
    old_url = "https://jobs.citi.com/job/hong-kong/wealth-citigold-summer-analyst/287/99664839024"
    new_url = "https://jobs.citi.com/job/hong-kong/wealth-citigold-summer-analyst/287/102161047888"
    editor = InlineBuffer.from_value(old_url)
    editor.select_all()
    assert editor.all_selected
    editor.insert(new_url)
    assert editor.value == new_url
    assert not editor.all_selected


def test_select_all_then_backspace_clears_only_field_value():
    editor = InlineBuffer.from_value("https://example.com/very/long/url")
    editor.select_all()
    editor.backspace()
    assert editor.value == ""
    assert editor.cursor == 0


def test_arrow_keys_exit_selection_without_erasing_text():
    editor = InlineBuffer.from_value("HSBC")
    editor.select_all()
    editor.move_left()
    assert not editor.all_selected
    assert editor.cursor == 0
    assert editor.value == "HSBC"
