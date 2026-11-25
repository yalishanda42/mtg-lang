import dataclasses

import pytest

from mtglang.ast import NP, Action, Num, SymRef, to_json, walk


def test_to_json_symref():
    assert to_json(SymRef(5, "◈")) == {"kind": "sym", "sym": "◈", "index": 5}


def test_to_json_nested_action():
    a = Action(verb=SymRef(1, "⤓"), args=(("amount", Num(1)),))
    j = to_json(a)
    assert j["kind"] == "action" and j["verb"]["sym"] == "⤓"
    assert j["args"] == {"amount": {"kind": "num", "value": 1, "sign": ""}}


def test_nodes_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        SymRef(1, "x").index = 2


def test_walk_yields_paths():
    np = NP(quant=SymRef(2, "◎"), heads=(SymRef(3, "♞"),))
    a = Action(verb=SymRef(1, "✖"), args=(("object", np),))
    paths = dict(walk(a))
    assert paths[""] is a
    assert paths["args.object"] is np
    assert paths["args.object.heads.0"] == SymRef(3, "♞")
