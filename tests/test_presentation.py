from career_job_manager.model import ApplicationRecord
from career_job_manager.presentation import (
    FILE_FIELDS,
    FORM_FIELDS,
    TEXT_FIELDS,
    display_field_value,
    render_field_line,
    render_home_lines,
    render_inline_selector_lines,
    selector_options,
    visible_form_fields,
)


def make_record(**overrides):
    data = {
        "id": "1",
        "company": "HSBC",
        "job": "Global Banking Graduate",
        "deadline": "2026-09-20 18:00",
        "action": "Wait",
        "target": "",
        "portal": "https://company.com/my-applications",
        "contact": "Jane Smith",
        "brochure": "",
        "form": "",
        "resume": "HSBC_Global-Banking-Graduate_Resume.docx",
        "letter": "",
    }
    data.update(overrides)
    record = ApplicationRecord(**data)
    record.validate()
    return record


def test_form_fields_are_plain_one_word_rows_in_expected_order():
    assert FORM_FIELDS == (
        "Action",
        "Company",
        "Job",
        "Deadline",
        "Target",
        "Brief",
        "Portal",
        "Contact",
        "Resume",
        "Letter",
        "Form",
        "Brochure",
        "DescriptionText",
    )
    assert TEXT_FIELDS == (
        "Company", "Job", "Deadline", "Target", "Brief", "Portal", "Contact", "DescriptionText"
    )
    assert FILE_FIELDS == ("Resume", "Letter", "Brochure", "Form")


def test_wait_and_archive_hide_target_other_actions_show_it():
    assert "Target" not in visible_form_fields("Wait")
    assert "Target" not in visible_form_fields("Archive")
    assert "Target" in visible_form_fields("Apply")
    assert "Target" in visible_form_fields("Take")
    assert "Target" in visible_form_fields("Go")
    assert "Target" in visible_form_fields("Respond")


def test_action_is_the_only_fixed_selector():
    assert selector_options("Action") == (
        "Apply", "Email", "Wait", "Go", "Take", "Check", "Archive",
    )
    assert selector_options("Status") == ()
    assert selector_options("Company") == ()


def test_field_line_uses_only_a_leading_cursor_marker_and_plain_text():
    assert render_field_line("Status", "Applied", selected=True) == "> Status       Applied"
    assert render_field_line("Action", "Wait", selected=False) == "  Action       Wait"


def test_all_file_fields_show_choose_when_empty():
    for field in FILE_FIELDS:
        assert display_field_value(field, "") == "View    Choose"


def test_home_render_uses_action_column_not_status_column():
    records = [
        make_record(id="1", company="HSBC", action="Wait"),
        make_record(id="2", company="BCG", job="Associate", action="Go", deadline="2026-09-25 14:00"),
    ]
    lines = render_home_lines(records, selected_index=1)
    assert "Action" in lines[0]
    assert "Status" not in lines[0]
    assert lines[1].startswith("  ")
    assert lines[2].startswith("> ")
    assert "Go" in lines[2]


def test_keyboard_contract_uses_right_for_selectors_and_disables_mouse():
    from career_job_manager.presentation import MOUSE_ENABLED, SELECTOR_ACTIVATION_KEYS

    assert SELECTOR_ACTIVATION_KEYS == ("right",)
    assert MOUSE_ENABLED is False


def test_inline_selector_keeps_all_option_text_at_exact_same_column():
    lines = render_inline_selector_lines(
        "Action",
        "Wait",
        ("Apply", "Wait", "Take"),
        selected_index=1,
    )
    assert lines == [
        "> Action       Wait              Apply",
        "                               > Wait",
        "                                 Take",
    ]
    option_starts = [line.index(option) for line, option in zip(lines, ("Apply", "Wait", "Take"))]
    assert option_starts == [33, 33, 33]


def test_existing_application_heading_is_job_identity_not_edit_label():
    from career_job_manager.presentation import application_heading

    record = make_record(company="HSBC", job="Global Banking Graduate")
    assert application_heading(record) == "HSBC — Global Banking Graduate"
    assert application_heading(None) == "ADD"


def test_description_file_choose_stays_aligned_and_text_preview_sits_below():
    from career_job_manager.presentation import (
        DESCRIPTION_TEXT_FIELD,
        render_description_text_line,
    )

    assert DESCRIPTION_TEXT_FIELD == "DescriptionText"
    assert render_field_line("Resume", "", selected=False) == "  Resume       View    Choose"
    assert render_field_line("Letter", "", selected=False) == "  Letter       View    Choose"
    assert render_field_line("Brochure", "", selected=False) == "  Brochure     View    Choose"
    assert render_field_line("Form", "", selected=False) == "  Form         View    Choose"

    preview = render_description_text_line("Short pasted description", selected=False)
    assert preview == "               Short pasted description"

    long_text = "A" * 300
    assert render_description_text_line(long_text).endswith(long_text)


def test_description_text_preserves_whitespace_in_view_and_editor():
    from career_job_manager.presentation import (
        render_description_editing_line,
        render_description_text_line,
    )

    raw = "First line\nSecond   line\tthird"
    assert render_description_text_line(raw, selected=False) == "               " + raw
    editing = render_description_editing_line(raw, cursor=len(raw))
    assert "First line\nSecond   line\tthird│" in editing
