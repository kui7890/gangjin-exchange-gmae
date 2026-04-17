import json
from urllib.parse import parse_qs, urlparse


def read_json_body(handler):
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length == 0:
        return {}

    raw_body = handler.rfile.read(content_length)
    if not raw_body:
        return {}

    return json.loads(raw_body.decode("utf-8"))


def send_json(handler, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def get_query_params(path):
    return parse_qs(urlparse(path).query)
