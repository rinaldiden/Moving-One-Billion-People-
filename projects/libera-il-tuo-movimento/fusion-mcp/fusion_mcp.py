#!/usr/bin/env python3
"""
fusion_mcp.py — Client per l'MCP NATIVO di Autodesk Fusion 360
==============================================================

Fusion 5.0 espone un server MCP integrato (Preferences > General > API >
"Fusion MCP Server"), di default su http://127.0.0.1:27182/mcp.
Questo client fa l'handshake MCP e chiama i suoi 4 tool ufficiali.

NON serve installare add-in: basta che in Fusion il "Fusion MCP Server" sia
spuntato e un documento sia aperto.

Uso (quello che lancia zio code):
    python3 fusion_mcp.py tools                 # elenca i tool MCP
    python3 fusion_mcp.py docs                  # documenti aperti
    python3 fusion_mcp.py recent                # documenti recenti
    python3 fusion_mcp.py projects              # progetti
    python3 fusion_mcp.py params                # parametri del design attivo
    python3 fusion_mcp.py info                  # riepilogo design attivo
    python3 fusion_mcp.py shot out.png [dir]    # screenshot (dir: iso-top-left, front, ...)
    python3 fusion_mcp.py script file.py        # esegue uno script (deve avere run(_context))
    python3 fusion_mcp.py apidoc <regex> [cat]  # cerca nella doc API Fusion
    python3 fusion_mcp.py save                   # salva il documento attivo
    python3 fusion_mcp.py raw <tool> '<json>'   # chiamata grezza a un tool

Solo libreria standard.
"""

import base64
import json
import sys
import urllib.request
import urllib.error

ENDPOINT = "http://127.0.0.1:27182/mcp"
HEADERS = {"Content-Type": "application/json",
           "Accept": "application/json, text/event-stream"}


class MCPError(Exception):
    pass


def _post(payload, session_id=None, timeout=125):
    headers = dict(HEADERS)
    if session_id:
        headers["MCP-Session-Id"] = session_id
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            sid = resp.headers.get("MCP-Session-Id")
            body = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise MCPError(f"MCP non raggiungibile ({e}). In Fusion: Preferences > "
                       f"General > API > 'Fusion MCP Server' spuntato? Documento aperto?")
    return sid, _parse_body(body)


def _parse_body(body):
    body = body.strip()
    if not body:
        return None
    # Streamable HTTP puo' rispondere in SSE ("data: {...}") o JSON puro
    if body.startswith("event:") or "data:" in body.split("\n", 1)[0]:
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return None
    return json.loads(body)


def connect():
    """Handshake MCP completo. Ritorna la session id."""
    sid, resp = _post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "zio-code", "version": "1.0"}},
    })
    if not sid:
        raise MCPError("initialize non ha restituito una session id")
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session_id=sid)
    return sid


def rpc(method, params=None, session_id=None, req_id=2):
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    _, resp = _post(payload, session_id=session_id)
    if resp and "error" in resp:
        raise MCPError(json.dumps(resp["error"], ensure_ascii=False))
    return resp.get("result") if resp else None


def call_tool(name, arguments, session_id):
    return rpc("tools/call", {"name": name, "arguments": arguments}, session_id=session_id)


def _text_of(result):
    """Estrae il testo/JSON da un risultato tool MCP (content: [{type:text,...}])."""
    if not isinstance(result, dict):
        return result
    parts = []
    for item in result.get("content", []):
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(parts) if parts else result


# --- script pronto per leggere i parametri del design attivo ------------------
PARAMS_SCRIPT = r'''
import adsk.core, adsk.fusion, json
def run(_context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    doc = app.activeDocument
    out = {"document": doc.name if doc else None, "hasDesign": design is not None}
    if design:
        um = design.unitsManager
        out["defaultUnits"] = um.defaultLengthUnits
        root = design.rootComponent
        out["rootComponent"] = root.name
        out["bodyCount"] = root.bRepBodies.count
        out["componentCount"] = design.allComponents.count
        ups = []
        for p in design.userParameters:
            ups.append({"name": p.name, "expression": p.expression,
                        "value": p.value, "unit": p.unit, "comment": p.comment})
        out["userParameters"] = ups
        out["userParameterCount"] = len(ups)
        out["modelParameterCount"] = design.allParameters.count
    print(json.dumps(out, ensure_ascii=False, indent=2))
'''

INFO_SCRIPT = PARAMS_SCRIPT  # stesso payload, riepilogo


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    try:
        sid = connect()
    except MCPError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
        return 2

    try:
        if cmd == "tools":
            res = rpc("tools/list", session_id=sid)
            print("\n".join(f"- {t['name']}" for t in res["tools"]))
        elif cmd == "docs":
            res = call_tool("fusion_mcp_read", {"queryType": "document", "operation": "open"}, sid)
            print(_text_of(res))
        elif cmd == "recent":
            res = call_tool("fusion_mcp_read", {"queryType": "document", "operation": "recent"}, sid)
            print(_text_of(res))
        elif cmd == "projects":
            res = call_tool("fusion_mcp_read", {"queryType": "projects"}, sid)
            print(_text_of(res))
        elif cmd in ("params", "info"):
            res = call_tool("fusion_mcp_execute",
                            {"featureType": "script", "object": {"script": PARAMS_SCRIPT}}, sid)
            print(_text_of(res))
        elif cmd == "script":
            if len(argv) < 2:
                print("Uso: script <file.py>"); return 1
            code = sys.stdin.read() if argv[1] == "-" else open(argv[1]).read()
            res = call_tool("fusion_mcp_execute",
                            {"featureType": "script", "object": {"script": code}}, sid)
            print(_text_of(res))
        elif cmd in ("shot", "screenshot"):
            if len(argv) < 2:
                print("Uso: shot <out.png> [direction]"); return 1
            args = {"queryType": "screenshot"}
            if len(argv) > 2:
                args["direction"] = argv[2]
            res = call_tool("fusion_mcp_read", args, sid)
            # il risultato contiene un'immagine base64
            img_b64 = None
            if isinstance(res, dict):
                for item in res.get("content", []):
                    if item.get("type") == "image":
                        img_b64 = item.get("data")
            if not img_b64:
                txt = _text_of(res)
                try:
                    img_b64 = json.loads(txt).get("data")
                except Exception:
                    pass
            if img_b64:
                with open(argv[1], "wb") as f:
                    f.write(base64.b64decode(img_b64))
                print(json.dumps({"ok": True, "path": argv[1]}))
            else:
                print(json.dumps({"ok": False, "raw": res}, ensure_ascii=False)[:2000])
        elif cmd == "apidoc":
            if len(argv) < 2:
                print("Uso: apidoc <regex> [class|member|description|all]"); return 1
            args = {"queryType": "apiDocumentation", "searchPattern": argv[1]}
            if len(argv) > 2:
                args["apiCategory"] = argv[2]
            res = call_tool("fusion_mcp_read", args, sid)
            print(_text_of(res))
        elif cmd == "save":
            res = call_tool("fusion_mcp_execute",
                            {"featureType": "document", "object": {"operation": "save"}}, sid)
            print(_text_of(res))
        elif cmd == "raw":
            if len(argv) < 3:
                print("Uso: raw <tool> '<json-args>'"); return 1
            res = call_tool(argv[1], json.loads(argv[2]), sid)
            print(_text_of(res))
        else:
            print(f"Comando sconosciuto: {cmd}\n{__doc__}")
            return 1
    except MCPError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
