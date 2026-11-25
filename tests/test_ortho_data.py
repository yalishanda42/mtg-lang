from mtglang.ortho import LISTS, data_path


def test_all_lists_present():
    for name in LISTS:
        p = data_path(name)
        text = p.read_text(encoding="utf-8")
        assert text.strip() and not text.startswith("﻿"), name
    assert "Petar Nedelev" in data_path("LICENSE.md").read_text(encoding="utf-8")
