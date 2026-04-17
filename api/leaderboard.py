from http.server import BaseHTTPRequestHandler

from api._http import send_json
from api.service import get_leaderboard


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            send_json(self, {"leaderboard": get_leaderboard()})
        except Exception as error:
            send_json(self, {"error": str(error)}, status=500)
