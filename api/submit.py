from http.server import BaseHTTPRequestHandler

try:
    from ._http import read_json_body, send_json
    from .service import parse_team_id, submit_answer
except ImportError:
    from _http import read_json_body, send_json
    from service import parse_team_id, submit_answer


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            payload = read_json_body(self)
            team_id = parse_team_id(payload.get("teamId"))
            quest_id = payload.get("questId", "")
            answer = payload.get("answer", "")

            if not quest_id or not answer:
                raise ValueError("퀘스트와 답을 모두 보내 주세요.")

            result = submit_answer(team_id, quest_id, answer)
            send_json(self, result)
        except ValueError as error:
            send_json(self, {"error": str(error)}, status=400)
        except Exception:
            send_json(self, {"error": "정답 제출을 처리하지 못했습니다."}, status=500)
