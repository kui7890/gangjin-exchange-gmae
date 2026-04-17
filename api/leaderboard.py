from http.server import BaseHTTPRequestHandler

try:
    from ._http import send_json
    from .service import get_leaderboard
except ImportError:
    from _http import send_json
    from service import get_leaderboard


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            send_json(self, {"leaderboard": get_leaderboard()})
        except Exception:
            send_json(self, {"error": "리더보드를 불러오지 못했습니다."}, status=500)
