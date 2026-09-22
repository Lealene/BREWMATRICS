#!/usr/bin/env python3
"""BREWMETRIC POS - coffee shop point-of-sale system (Python 3.8+, no dependencies).

Run:   python brewmetric.py [port]      then open http://localhost:8000
All logic (pricing, cart, cup visualizer, prep queue, ingredient levels) and all
HTML/SVG rendering happen in Python. State is saved to brewmetric_data.json.
"""
import json, os, sys
from html import escape
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brewmetric_data.json")
CSS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brewmetric.css")

# size -> (price add-on, scale factor, dose in g, cup fill ratio)
SIZES = {"Small": (0, .75, 14, .55), "Medium": (20, .9, 16, .7), "Large": (40, 1, 18, .85)}
# (name, price, ingredient use)
TOPPINGS = [("Strawberry", 25, {}), ("Cream", 30, {"crema": 3}), ("Marshmallow", 20, {}),
            ("Blueberry", 25, {}), ("Chocolate", 50, {"chocolate": 4}), ("Sprinkles", 15, {}),
            ("Mango", 30, {}), ("Graham", 20, {}), ("Banana", 30, {}), ("Caramel", 25, {}),
            ("Hazelnut", 30, {}), ("Cinnamon", 10, {}), ("Whipped Cream", 30, {"crema": 3}),
            ("Oreo Crumbs", 25, {}), ("Cheese Foam", 35, {"crema": 2})]
# (name, base price, kind e=espresso-based / m=milk-based, value A, value B)
DRINKS = [("Espresso", 130, "e", 18, 130), ("Latte", 150, "m", 240, 12), ("Crema", 140, "e", 18, 150),
          ("Vanilla Latte", 160, "m", 240, 15), ("Chocolate Shake", 170, "m", 300, 25),
          ("Black Coffee", 90, "e", 20, 300), ("Doppio", 160, "e", 36, 130), ("Red Eye", 150, "e", 22, 250),
          ("Macchiato", 150, "m", 60, 8), ("Americano", 110, "e", 18, 250), ("Mocha", 170, "m", 220, 20),
          ("Flat White", 160, "m", 180, 10), ("Cortado", 150, "m", 90, 8), ("Affogato", 180, "e", 18, 90),
          ("Iced Latte", 160, "m", 240, 12), ("Cold Brew", 150, "e", 30, 350)]
USE = {"e": {"coffee": 3, "crema": 2}, "m": {"coffee": 2}}
LIST, PAGE = {"tp": TOPPINGS, "dr": DRINKS}, {"tp": 9, "dr": 12}
STATUS = {"q": "Queued", "b": "Brewing", "d": "Done"}
BTN = {"q": "START", "b": "MARK DONE", "d": "✓ DONE"}


class Store:
    def __init__(self):
        self.size, self.msg = "Large", ""
        self.cart = {"tp": {}, "dr": {}}
        self.page = {"tp": 0, "dr": 0}
        self.queue = [dict(id=1, no=1, name="Double Shot Espresso (Large)", p=[["Grind", "18g"], ["Water", "130ml"]], st="d", use={}),
                      dict(id=2, no=2, name="Latte Art: Heart", p=[["Milk", "240ml"], ["Sugar", "12g"]], st="b", use={"coffee": 2}),
                      dict(id=3, no=3, name="Banana", p=[["Portion", "2 pc"], ["Prep", "Fresh"]], st="q", use={})]
        self.order_no, self.uid, self.sel = 3, 3, 1
        self.levels = {"coffee": 85, "crema": 92, "chocolate": 76}
        try:
            with open(DATA) as f:
                d = json.load(f)
            self.queue, self.order_no, self.uid, self.levels = d["queue"], d["order_no"], d["uid"], d["levels"]
            self.sel = self.queue[0]["id"] if self.queue else None
        except (OSError, ValueError, KeyError):
            pass

    def save(self):
        with open(DATA, "w") as f:
            json.dump(dict(queue=self.queue, order_no=self.order_no, uid=self.uid, levels=self.levels), f)

    def calc(self):
        add, lines, total = SIZES[self.size][0], [], 0
        for i, n in sorted(self.cart["dr"].items()):
            name, price = DRINKS[i][:2]
            lines.append((f"{name} ({self.size}) — {n}x", (price + add) * n))
        for i, n in sorted(self.cart["tp"].items()):
            name, price = TOPPINGS[i][:2]
            extra = " (Dose: 12ml)" if name == "Chocolate" else ""
            lines.append((f"{name.upper()}{extra} — {n}x", price * n))
        return lines, sum(p for _, p in lines)

    def add_ticket(self, name, params, use, n):
        self.uid += 1
        self.queue.append(dict(id=self.uid, no=self.order_no, name=name, p=params, st="q",
                               use={k: v * n for k, v in use.items()}))

    def send(self):
        if not self.calc()[0]:
            self.msg = "Add at least one item first"
            return
        self.order_no += 1
        scale = SIZES[self.size][1]
        for i, n in sorted(self.cart["dr"].items()):
            name, _, kind, a, b = DRINKS[i]
            params = ([["Grind", f"{round(a * scale)}g"], ["Water", f"{round(b * scale)}ml"]] if kind == "e"
                      else [["Milk", f"{round(a * scale)}ml"], ["Sugar", f"{b}g"]])
            self.add_ticket(f"{name} ({self.size})" + (f" ×{n}" if n > 1 else ""), params, USE[kind], n)
        for i, n in sorted(self.cart["tp"].items()):
            name, _, use = TOPPINGS[i]
            self.add_ticket(name + (f" ×{n}" if n > 1 else ""), [["Portion", f"{n} pc"], ["Prep", "Fresh"]], use, n)
        self.cart = {"tp": {}, "dr": {}}
        self.msg = f"Order #{self.order_no:02d} sent to prep"
        self.save()

    def act(self, cmd):
        p = cmd.split(":")
        a = p[0]
        if a in ("inc", "dec"):
            c, i = self.cart[p[1]], int(p[2])
            n = max(0, c.get(i, 0) + (1 if a == "inc" else -1))
            c[i] = n
            if not n:
                del c[i]
        elif a == "size" and p[1] in SIZES:
            self.size = p[1]
        elif a == "page":
            k = p[1]
            last = -(-len(LIST[k]) // PAGE[k]) - 1
            self.page[k] = max(0, min(last, self.page[k] + int(p[2])))
        elif a == "reset":
            self.cart = {"tp": {}, "dr": {}}
        elif a == "send":
            self.send()
        elif a == "sel":
            self.sel = int(p[1])
        elif a == "adv":
            q = next((x for x in self.queue if x["id"] == int(p[1])), None)
            if q and q["st"] != "d":
                self.sel = q["id"]
                q["st"] = "b" if q["st"] == "q" else "d"
                if q["st"] == "d":
                    for k, v in q["use"].items():
                        self.levels[k] = max(0, self.levels[k] - v)
                    self.msg = f"{q['name']} is done"
                self.save()
        elif a == "clear":
            self.queue = [q for q in self.queue if q["st"] != "d"]
            if not any(q["id"] == self.sel for q in self.queue):
                self.sel = self.queue[0]["id"] if self.queue else None
            self.save()
        elif a == "refill" and p[1] in self.levels:
            self.levels[p[1]] = 100
            self.save()


store = Store()


# ---------------------------------------------------------------- rendering

MUG = ('<svg viewBox="0 0 260 300" role="img" aria-label="Ceramic coffee mug"><rect width="260" height="300" fill="#f3f2f0"/>'
       '<ellipse cx="130" cy="234" rx="78" ry="8" fill="#0001"/>'
       '<path d="M62 138Q28 132 32 162Q36 190 70 180" fill="none" stroke="#dcdcd6" stroke-width="11" stroke-linecap="round"/>'
       '<path d="M198 138Q232 132 228 162Q224 190 190 180" fill="none" stroke="#dcdcd6" stroke-width="11" stroke-linecap="round"/>'
       '<path d="M60 120H200V152Q200 218 130 230Q60 218 60 152Z" fill="#ebebe7"/>'
       '<path d="M84 196Q130 212 176 196L168 222Q130 232 92 222Z" fill="#c9a882"/><ellipse cx="130" cy="120" rx="70" ry="8" fill="#d8d8d3"/></svg>')


def shell(path, body):
    badge = sum(q["st"] != "d" for q in store.queue)
    flash = f'<div class="toast" role="status">{escape(store.msg)}</div>' if store.msg else ""
    store.msg = ""
    on = lambda p: ' class="on"' if p == path else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>BREWMETRIC POS</title><link rel="stylesheet" href="/brewmetric.css"></head><body><form method="post" action="{path}">'
            f'<header class="top"><span class="logo">■ LOGO</span><nav><a href="/"{on("/")}>Home</a>'
            f'<a href="/prep"{on("/prep")}>Preparation Screen<span class="badge">{badge}</span></a></nav></header>{body}'
            f'<footer><div class="m">[ © 2026 BREWMETRIC POS SYSTEM ]<br>[ SYSTEM_VERSION: 1.0.0 ]</div><div class="w">BREWMETRIC</div></footer>'
            f'</form>{flash}</body></html>')


def ctr(kind, i):
    n = store.cart[kind].get(i, 0)
    return (f'<div class="ctr"><button name="do" value="dec:{kind}:{i}" aria-label="Remove one">-</button><b>{n}</b>'
            f'<button name="do" value="inc:{kind}:{i}" aria-label="Add one">+</button></div>')


def carousel(kind, cols, extra):
    pg, size = store.page[kind], PAGE[kind]
    last = -(-len(LIST[kind]) // size) - 1
    cells = "".join(f'<div class="cell">{it[0]}<small>₱{it[1] + extra}</small>{ctr(kind, i)}</div>'
                    for i, it in enumerate(LIST[kind]) if pg * size <= i < pg * size + size)
    d = lambda ok, delta, sym: f'<button class="arr" name="do" value="page:{kind}:{delta}" {"" if ok else "disabled"} aria-label="Page">{sym}</button>'
    return f'<div class="car">{d(pg > 0, -1, "←")}<div class="grid {cols}">{cells}</div>{d(pg < last, 1, "→")}</div>'


def cup_svg():
    s = store
    fill = SIZES[s.size][3]
    has = lambda n: any(TOPPINGS[i][0] == n for i in s.cart["tp"])
    kinds = {DRINKS[i][2] for i in s.cart["dr"]}
    fruit = any(has(n) for n in ("Strawberry", "Blueberry", "Mango", "Banana"))
    other = any(TOPPINGS[i][0] not in ("Chocolate", "Cream", "Strawberry", "Blueberry", "Mango", "Banana") for i in s.cart["tp"])
    layers = [(bool(kinds), "#4b2a18", 3), ("m" in kinds or has("Cream") or has("Whipped Cream") or has("Cheese Foam"), "#e6cfae", 2),
              (has("Chocolate"), "#2e1a12", 1), (fruit, "#d9a441", 1), (other, "#c98f6b", 1)]
    layers = [l for l in layers if l[0]]
    total_w, y, rects = sum(l[2] for l in layers), 190.0, ""
    for _, color, w in layers:
        h = 130 * fill * w / total_w
        y -= h
        rects += f'<rect x="40" y="{y:.1f}" width="120" height="{h:.1f}" fill="{color}"/>'
    st = 'fill="none" stroke="currentColor" stroke-width="4"'
    return (f'<svg viewBox="0 0 200 215" role="img" aria-label="Cup preview, {s.size}"><defs><clipPath id="cc"><path d="M50 60H150L138 190H62Z"/></clipPath></defs>'
            f'<g clip-path="url(#cc)">{rects}</g><path d="M50 60H150L138 190H62Z" {st}/><rect x="42" y="46" width="116" height="14" {st}/>'
            f'<rect x="55" y="34" width="90" height="12" {st}/><rect x="66" y="190" width="68" height="14" {st}/>'
            f'<text x="100" y="84" text-anchor="middle" font-family="Courier New,monospace" font-size="11" fill="currentColor">{s.size.upper()}</text></svg>')


def home():
    s = store
    add, _, dose, _ = SIZES[s.size]
    lines, total = s.calc()
    n_drinks = sum(s.cart["dr"].values())
    n_esp = sum(n for i, n in s.cart["dr"].items() if DRINKS[i][2] == "e")
    milk = any(DRINKS[i][2] == "m" for i in s.cart["dr"])
    crema = min(98, 78 + n_esp * 6) if n_esp else 0
    extraction = f"{.12 + .03 * n_esp:.3f}" if n_esp else "0.000"
    layering = f"{sum(s.cart['tp'].values()) * .05 + (.1 if milk else 0):.2f}"
    macro = "".join(f"<div>{escape(t.split(' (Dose')[0])}</div>" for t, _ in lines) or "<div>Nothing added yet</div>"
    tabs = "".join(f'<button name="do" value="size:{k}"{" class=on" if k == s.size else ""}>{k.upper()}</button>' for k in reversed(list(SIZES)))
    rows = "".join(f'<div class="ln"><span>{escape(t)}</span><span>{p}</span></div>' for t, p in lines) \
        or '<div class="ln">No items yet. Add a drink to start an order.</div>'
    body = f"""<div class="wrap" id="tp"><div class="hgrid"><div>
<h2 class="t">Size &amp; extra toppings / Flavor</h2>
<div class="tan"><div class="sizes">{tabs}</div>{carousel("tp", "g3", 0)}</div>
<h3 class="vis">Cup Visualizer</h3><p class="sub">Real-time visualization of drink composition and extraction metrics.</p>
<div class="metrics">[CREMA: {crema}%]<br>[EXTRACTION: {extraction}]<br>[DOSE: {n_drinks * dose}G]<br>[LAYERING: {layering}]</div></div>
<div class="cupbox"><div class="mono" style="font-size:10px;margin-bottom:8px">MACRO ADD-ONS</div>{cup_svg()}<div class="macro">{macro}</div></div></div></div>
<div class="band" id="dr"><div class="wrap"><h2 class="t" style="font-size:26px">ORDER DRINK'S</h2>
<p class="sub" style="margin:6px auto 0">Configure your order with precise extraction parameters and layering specifications.</p>
<div class="cnt">coffee Drink</div>{carousel("dr", "g4", add)}</div></div>
<div class="sumband" id="sum"><div class="wrap"><div><h2>ORDER SUMMARY</h2><div style="margin-top:14px">{rows}</div><div class="total">TOTAL: {total} Ph</div></div>
<div class="acts"><button name="do" value="reset">RESET</button><button class="go" name="do" value="send">SEND TO PREP</button></div></div></div>"""
    return shell("/", body)


def prep():
    s = store
    rows = "".join(
        f'<div class="qrow {q["st"]}{" sel" if q["id"] == s.sel else ""}"><button class="pick" name="do" value="sel:{q["id"]}">'
        f'<span class="no">{q["no"]:02d}</span><span><span class="nm">{escape(q["name"])}</span><span class="params">'
        + "".join(f"<span><small>{k}:</small>{v}</span>" for k, v in q["p"])
        + f'</span></span></button><button class="st" name="do" value="adv:{q["id"]}"{" disabled" if q["st"] == "d" else ""}>{BTN[q["st"]]}</button></div>'
        for q in s.queue) or '<div class="empty">Queue is empty. Send an order from Home to see it here.</div>'
    gauges = "".join(
        f'<div class="gauge{" low" if s.levels[k] < 20 else ""}"><small>{k.upper()}:</small><b>{s.levels[k]}%</b>'
        f'<div class="bar"><i style="width:{s.levels[k]}%"></i></div><button class="link" name="do" value="refill:{k}">Refill</button></div>'
        for k in ("coffee", "crema", "chocolate"))
    q = next((x for x in s.queue if x["id"] == s.sel), None)
    spec = (f'ORDER:<br>{escape(q["name"])} - {STATUS[q["st"]]}<br>TICKET: #{q["no"]:02d}<br>'
            + "<br>".join(f"{k.upper()}: {v}" for k, v in q["p"])) if q else "Select an order from the queue."
    body = f"""<div class="wrap"><h2 class="t">Active Orders Queue</h2>
<p class="sub">Real-time extraction tracking and ingredient level monitoring for precision barista workflow.</p>
<div class="pgrid"><div>{rows}<button class="link" name="do" value="clear" style="margin-top:14px">Clear done orders</button></div><div>{gauges}</div></div></div>
<div class="band"><div class="spec"><div><h2>DRINK<br>SPECIFICATION</h2><div class="o">{spec}</div></div><div>{MUG}</div></div></div>"""
    return shell("/prep", body)


# ------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body=b"", **headers):
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k.replace("_", "-"), v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/brewmetric.css":
            try:
                with open(CSS_FILE, "rb") as f:
                    data = f.read()
                return self.reply(200, data, Content_Type="text/css; charset=utf-8")
            except OSError:
                return self.reply(404, b"Not found")
        if path not in ("/", "/prep"):
            return self.reply(404, b"Not found")
        self.reply(200, (prep() if path == "/prep" else home()).encode(), Content_Type="text/html; charset=utf-8")

    def do_POST(self):
        path = self.path if self.path in ("/", "/prep") else "/"
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        cmd = parse_qs(raw).get("do", [""])[0]
        try:
            store.act(cmd)
        except (ValueError, IndexError, KeyError):
            pass
        part = cmd.split(":")
        anchor = "" if path == "/prep" else "#" + (part[1] if part[0] in ("inc", "dec", "page") else "sum" if part[0] in ("send", "reset") else "tp")
        self.reply(303, Location=path + anchor)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    url = f"http://localhost:{port}"
    print(f"BREWMETRIC POS running at {url}  (Ctrl+C to stop)")
    print(f"Open {url} manually in your browser - auto-open removed")
    try:
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")