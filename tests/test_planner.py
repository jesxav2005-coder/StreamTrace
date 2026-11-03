import json

from app.planner import parse_plan

ORIGINAL = "how does acks=all work"


def test_parse_plan_reads_json_and_drops_unknown_modules():
    text = 'Sure: [{"question": "handle produce", "modules": ["core", "nope"]}]'
    assert parse_plan(text, ORIGINAL) == [{"question": "handle produce", "modules": ["core"]}]


def test_parse_plan_falls_back_on_bad_output():
    assert parse_plan("not json at all", ORIGINAL) == [{"question": ORIGINAL, "modules": []}]


def test_parse_plan_limits_steps():
    text = json.dumps([{"question": f"q{i}"} for i in range(9)])
    assert len(parse_plan(text, ORIGINAL)) == 5
