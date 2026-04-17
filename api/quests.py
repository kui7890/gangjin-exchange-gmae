from http.server import BaseHTTPRequestHandler

try:
    from ._http import get_query_params, send_json
    from .service import get_quests_for_team, parse_team_id
except ImportError:
    from _http import get_query_params, send_json
    from service import get_quests_for_team, parse_team_id


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            params = get_query_params(self.path)
            raw_team_id = params.get("teamId", ["1"])[0]
            team_id = parse_team_id(raw_team_id)
            quests = get_quests_for_team(team_id)
            send_json(self, {"quests": quests})
        except ValueError as error:
            send_json(self, {"error": str(error)}, status=400)
        except Exception:
            send_json(self, {"error": "퀘스트를 불러오지 못했습니다."}, status=500)
