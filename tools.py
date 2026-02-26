import json
import httpx
import asyncio
from typing import Any, Dict
import math
import ast
import operator as _operator

class ToolRegistry:
    def __init__(self):
        self._registry = {}

    def register(self, name: str, func, description: str = ""):
        self._registry[name] = {"callable": func, "description": description}

    def get(self, name: str):
        return self._registry.get(name)

    def list(self):
        return {k: v["description"] for k, v in self._registry.items()}

registry = ToolRegistry()


async def run_tool(name: str, args: Dict[str, Any]):
    """Run a registered tool asynchronously. Returns a JSON-serializable result."""
    entry = registry.get(name)
    if not entry:
        raise ValueError(f"Tool not found: {name}")
    func = entry["callable"]
    if asyncio.iscoroutinefunction(func):
        return await func(args)
    else:
        # run sync function in threadpool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(args))


# --- Example tools ---
async def weather_tool(args: Dict[str, Any]):
    """Simple weather tool using wttr.in (no API key). args: { location: 'City' }

    Returns a short text summary. Good for PoC and local use.
    """
    location = args.get("location") or args.get("q") or "" 
    if not location:
        # If no location provided, try to infer from args or return an error
        return {"error": "missing location"}
    # Use wttr.in simple text output. This endpoint is free and requires no key.
    url = f"https://wttr.in/{httpx.utils.quote(location)}?format=%l:+%c+%t"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers={"User-Agent": "ALICE-Tools/1.0"})
            if r.status_code == 200:
                text = r.text.strip()
                return {"result": text}
            else:
                return {"error": f"http {r.status_code}", "body": r.text}
    except Exception as e:
        return {"error": str(e)}


def echo_tool(args: Dict[str, Any]):
    return {"result": args}


# register example tools
registry.register("weather", weather_tool, "Fetch simple weather summary from wttr.in")
registry.register("echo", echo_tool, "Echo supplied args (useful for testing)")


# --- Additional example tools ---
async def web_search_tool(args: Dict[str, Any]):
    """Simple web search using DuckDuckGo Instant Answer API.

    args: { q: 'search terms' }
    Returns a small summary and the first related topic titles.
    """
    q = args.get("q") or args.get("query") or args.get("q")
    if not q:
        return {"error": "missing query"}
    # DuckDuckGo Instant Answer API (no API key) returns JSON with AbstractText
    url = "https://api.duckduckgo.com/"
    params = {"q": q, "format": "json", "no_html": 1, "skip_disambig": 1}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params, headers={"User-Agent": "ALICE-Tools/1.0"})
            if r.status_code != 200:
                return {"error": f"http {r.status_code}", "body": r.text}
            j = r.json()
            summary = j.get("AbstractText") or j.get("Abstract") or ""
            related = []
            for item in j.get("RelatedTopics", [])[:5]:
                if isinstance(item, dict):
                    txt = item.get("Text") or item.get("FirstURL")
                    if txt:
                        related.append(txt)
            return {"result": {"summary": summary, "related": related}}
    except Exception as e:
        return {"error": str(e)}


def _safe_eval_arith(expr: str):
    """Evaluate a simple arithmetic expression safely using ast.

    Supports numbers, + - * / **, parentheses, and math functions from `math`.
    """
    allowed_names = {k: getattr(math, k) for k in dir(math) if not k.startswith("__")}
    allowed_names.update({"abs": abs, "round": round})

    operators = {
        ast.Add: _operator.add,
        ast.Sub: _operator.sub,
        ast.Mult: _operator.mul,
        ast.Div: _operator.truediv,
        ast.Pow: _operator.pow,
        ast.USub: _operator.neg,
        ast.UAdd: _operator.pos,
        ast.Mod: _operator.mod,
    }

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("unsupported constant")
        if isinstance(node, ast.BinOp):
            op = type(node.op)
            if op not in operators:
                raise ValueError("unsupported operator")
            return operators[op](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = type(node.op)
            if op not in operators:
                raise ValueError("unsupported unary op")
            return operators[op](_eval(node.operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("only named functions allowed")
            func_name = node.func.id
            if func_name not in allowed_names:
                raise ValueError("function not allowed")
            func = allowed_names[func_name]
            args = [_eval(a) for a in node.args]
            return func(*args)
        raise ValueError(f"unsupported expression: {type(node)}")

    node = ast.parse(expr, mode="eval")
    return _eval(node)


def calc_tool(args: Dict[str, Any]):
    expr = args.get("expr") or args.get("expression") or ""
    if not expr:
        return {"error": "missing expression"}
    try:
        res = _safe_eval_arith(expr)
        return {"result": res}
    except Exception as e:
        return {"error": str(e)}


def time_tool(args: Dict[str, Any]):
    import datetime
    tz = args.get("tz") or args.get("timezone")
    now = datetime.datetime.now()
    return {"result": now.isoformat(), "tz": str(tz) if tz else None}


registry.register("search", web_search_tool, "Web search using DuckDuckGo Instant Answer API")
registry.register("calc", calc_tool, "Safe arithmetic calculator")
registry.register("time", time_tool, "Local time (simple)")
