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


def test_portal_and_target_auto_select_for_replacement():
    from career_job_manager.editing import editor_for_field

    for field in ("Portal", "Target"):
        editor = editor_for_field(field, "https://example.com/old")
        assert editor.all_selected
        editor.insert("https://example.com/new")
        assert editor.value == "https://example.com/new"
        assert not editor.all_selected


def test_url_selection_backspace_clears_entire_field():
    from career_job_manager.editing import editor_for_field

    editor = editor_for_field("Portal", "https://example.com/old")
    editor.backspace()
    assert editor.value == ""
    assert editor.cursor == 0


def test_non_url_fields_do_not_auto_select():
    from career_job_manager.editing import editor_for_field

    editor = editor_for_field("Company", "Citi")
    assert not editor.all_selected
    assert editor.cursor == 0
    editor.insert("Old ")
    assert editor.value == "Old Citi"


def test_arrow_cancels_url_selection_without_deleting_value():
    from career_job_manager.editing import editor_for_field

    editor = editor_for_field("Portal", "https://example.com")
    editor.move_right()
    assert editor.cursor == len(editor.value)
    assert not editor.all_selected
    editor.insert("/jobs")
    assert editor.value == "https://example.com/jobs"


def test_next_auto_selects_for_one_step_replacement():
    from career_job_manager.editing import editor_for_field

    editor = editor_for_field("Next", "2026-11-15")
    assert editor.all_selected
    editor.insert("ASAP")
    assert editor.value == "ASAP"
    assert not editor.all_selected
