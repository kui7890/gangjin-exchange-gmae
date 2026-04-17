from http.server import BaseHTTPRequestHandler

from api._http import read_json_body, send_json
from api.service import reset_game


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            payload = read_json_body(self)
            if payload.get("confirm") is not True:
                raise ValueError("초기화 확인 정보가 필요합니다.")

            leaderboard = reset_game()
            send_json(
                self,
                {
                    "message": "새 수업을 위해 점수를 초기화했어요.",
                    "leaderboard": leaderboard,
                },
            )
        except ValueError as error:
            send_json(self, {"error": str(error)}, status=400)
        except Exception:
            send_json(self, {"error": "초기화를 처리하지 못했습니다."}, status=500)
