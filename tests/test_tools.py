import asyncio
import math
import re
import tools


def test_registry_has_examples():
    # Ensure example tools are registered
    assert tools.registry.get("echo") is not None
    assert tools.registry.get("calc") is not None
    assert tools.registry.get("time") is not None


def test_echo_tool_via_run_tool():
    # run_tool is async; run it via asyncio.run
    res = asyncio.run(tools.run_tool("echo", {"foo": "bar"}))
    assert isinstance(res, dict)
    assert res.get("result") == {"foo": "bar"}


def test_calc_tool_basic_arithmetic():
    r = tools.calc_tool({"expr": "2 + 3 * 4"})
    assert "result" in r
    assert r["result"] == 14


def test_calc_tool_math_functions():
    # test a math function (sin(0) -> 0.0)
    r = tools.calc_tool({"expr": "sin(0)"})
    assert "result" in r
    # allow small floating rounding
    assert abs(r["result"] - 0.0) < 1e-9


def test_calc_tool_invalid_expression():
    # unsupported names should return an error
    r = tools.calc_tool({"expr": "__import__('os').system('echo hi')"})
    assert "error" in r


def test_time_tool():
    r = tools.time_tool({})
    assert "result" in r
    # basic ISO datetime format check
    assert re.match(r"\d{4}-\d{2}-\d{2}T", r["result"])
