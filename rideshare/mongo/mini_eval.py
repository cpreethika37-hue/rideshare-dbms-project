"""Tiny evaluator for the aggregation-expression subset used in mongo_demo.py.
mongomock lacks $range/$reduce/$round, so when no MongoDB server is available the SAME
expression object that is sent to MongoDB is evaluated here, document by document."""
import math
def ev(e, doc, env=None):
    env = env or {}
    if isinstance(e, str):
        if e.startswith("$$"):
            return env[e[2:]]
        if e.startswith("$"):
            cur = [doc]
            for part in e[1:].split("."):
                cur = [x for c in cur for x in (c if isinstance(c, list) else [c])]
                cur = [c[part] for c in cur]
            return cur if len(e[1:].split(".")) > 1 and isinstance(doc.get(e[1:].split(".")[0]), list) else cur[0]
        return e
    if isinstance(e, (int, float)): return e
    if isinstance(e, list): return [ev(x, doc, env) for x in e]
    (op, a), = e.items()
    A = lambda x=a: ev(x, doc, env)
    if op == "$map":
        return [ev(a["in"], doc, {**env, a["as"]: v}) for v in ev(a["input"], doc, env)]
    if op == "$range": lo, hi = A(); return list(range(int(lo), int(hi)))
    if op == "$sum": v = A(); return sum(v) if isinstance(v, list) else v
    if op == "$size": return len(A())
    if op == "$arrayElemAt": arr, i = A(); return arr[int(i)]
    if op == "$subtract": x, y = A(); return x - y
    if op == "$add": return sum(A())
    if op == "$multiply": return math.prod(A())
    if op == "$divide": x, y = A(); return x / y
    if op == "$pow": x, y = A(); return x ** y
    if op == "$sin": return math.sin(A())
    if op == "$cos": return math.cos(A())
    if op == "$asin": return math.asin(A())
    if op == "$sqrt": return math.sqrt(A())
    if op == "$degreesToRadians": return math.radians(A())
    raise NotImplementedError(op)
