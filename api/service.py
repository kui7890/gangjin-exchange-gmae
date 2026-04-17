import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from urllib import error, parse, request

try:
    from ._quest_bank import QUEST_BANK
except ImportError:
    from _quest_bank import QUEST_BANK


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOCAL_DB_PATH = DATA_DIR / "gangjin_exchange_game.db"
VERCEL_DB_PATH = Path("/tmp/gangjin_exchange_game.db")

TEAM_SEED = [
    (1, "1모둠", "#cf7b29"),
    (2, "2모둠", "#456b45"),
    (3, "3모둠", "#2f6f9f"),
    (4, "4모둠", "#8e5f91"),
]


def parse_team_id(raw_value: str) -> int:
    try:
        team_id = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError("모둠 번호가 올바르지 않습니다.")

    if team_id not in {1, 2, 3, 4}:
        raise ValueError("모둠 번호는 1부터 4 사이여야 합니다.")

    return team_id


def get_quests_for_team(team_id: int) -> List[Dict]:
    solved_ids = set(get_solved_quest_ids(team_id))
    ordered_bank = sorted(QUEST_BANK, key=lambda item: (-item["points"], item["title"]))

    return [
        {
            "id": quest["id"],
            "region": quest["region"],
            "title": quest["title"],
            "exchange": quest["exchange"],
            "question": quest["question"],
            "options": quest["options"],
            "points": quest["points"],
            "solvedBySelectedTeam": quest["id"] in solved_ids,
        }
        for quest in ordered_bank
    ]


def get_leaderboard() -> List[Dict]:
    if use_supabase():
        return supabase_get_leaderboard()

    initialize_local_database()

    with get_local_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                color,
                score,
                completed_count
            FROM teams
            ORDER BY score DESC, completed_count DESC, id ASC
            """
        ).fetchall()

    return [normalize_team_row(dict(row)) for row in rows]


def submit_answer(team_id: int, quest_id: str, answer: str) -> Dict:
    quest = find_quest(quest_id)
    if quest is None:
        raise ValueError("퀘스트를 찾을 수 없습니다.")

    correct_option = next(
        (option for option in quest["options"] if option["id"] == quest["answer"]),
        None,
    )
    correct_label = correct_option["text"] if correct_option else quest["answer"]

    if answer != quest["answer"]:
        return {
            "correct": False,
            "awardedPoints": 0,
            "message": f"아쉽지만 틀렸어요. {quest['explanation']}",
            "correctAnswerLabel": correct_label,
            "leaderboard": get_leaderboard(),
        }

    if use_supabase():
        awarded_points = supabase_submit_correct_answer(team_id, quest_id, quest["points"])
    else:
        awarded_points = local_submit_correct_answer(team_id, quest_id, quest["points"])

    if awarded_points == 0:
        return {
            "correct": True,
            "awardedPoints": 0,
            "message": f"{quest['title']} 퀘스트는 이미 해결했어요. 설명을 다시 읽어 보세요. {quest['explanation']}",
            "correctAnswerLabel": correct_label,
            "leaderboard": get_leaderboard(),
        }

    return {
        "correct": True,
        "awardedPoints": awarded_points,
        "message": f"정답입니다. {awarded_points}점을 얻었어요. {quest['explanation']}",
        "correctAnswerLabel": correct_label,
        "leaderboard": get_leaderboard(),
    }


def reset_game() -> List[Dict]:
    if use_supabase():
        supabase_reset_game()
        return get_leaderboard()

    initialize_local_database()
    with get_local_connection() as conn:
        conn.execute("DELETE FROM submissions")
        conn.execute("UPDATE teams SET score = 0, completed_count = 0")
        conn.commit()

    return get_leaderboard()


def find_quest(quest_id: str) -> Optional[Dict]:
    return next((quest for quest in QUEST_BANK if quest["id"] == quest_id), None)


def get_solved_quest_ids(team_id: int) -> List[str]:
    if use_supabase():
        rows = supabase_get_team_submissions(team_id)
        return [row["quest_id"] for row in rows]

    initialize_local_database()
    with get_local_connection() as conn:
        rows = conn.execute(
            "SELECT quest_id FROM submissions WHERE team_id = ?",
            (team_id,),
        ).fetchall()
    return [row["quest_id"] for row in rows]


def get_local_connection() -> sqlite3.Connection:
    db_path = VERCEL_DB_PATH if os.getenv("VERCEL") else LOCAL_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_local_database() -> None:
    with get_local_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                completed_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                quest_id TEXT NOT NULL,
                awarded_points INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, quest_id),
                FOREIGN KEY(team_id) REFERENCES teams(id)
            );
            """
        )

        team_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(teams)").fetchall()
        }
        if "score" not in team_columns:
            conn.execute("ALTER TABLE teams ADD COLUMN score INTEGER NOT NULL DEFAULT 0")
        if "completed_count" not in team_columns:
            conn.execute(
                "ALTER TABLE teams ADD COLUMN completed_count INTEGER NOT NULL DEFAULT 0"
            )

        conn.executemany(
            """
            INSERT INTO teams (id, name, color, score, completed_count)
            VALUES (?, ?, ?, 0, 0)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                color = excluded.color
            """,
            TEAM_SEED,
        )
        conn.commit()


def local_submit_correct_answer(team_id: int, quest_id: str, points: int) -> int:
    initialize_local_database()

    with get_local_connection() as conn:
        already_solved = conn.execute(
            "SELECT 1 FROM submissions WHERE team_id = ? AND quest_id = ?",
            (team_id, quest_id),
        ).fetchone()

        if already_solved is not None:
            return 0

        conn.execute(
            """
            INSERT INTO submissions (team_id, quest_id, awarded_points)
            VALUES (?, ?, ?)
            """,
            (team_id, quest_id, points),
        )
        conn.execute(
            """
            UPDATE teams
            SET
                score = score + ?,
                completed_count = completed_count + 1
            WHERE id = ?
            """,
            (points, team_id),
        )
        conn.commit()

    return points


def use_supabase() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def supabase_headers(prefer_return: Optional[str] = None) -> Dict[str, str]:
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    if prefer_return:
        headers["Prefer"] = prefer_return
    return headers


def supabase_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    payload: Optional[Dict] = None,
    prefer_return: Optional[str] = None,
):
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("SUPABASE_URL 환경 변수가 필요합니다.")

    query = f"?{parse.urlencode(params)}" if params else ""
    url = f"{base_url}/rest/v1/{endpoint}{query}"
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = request.Request(
        url,
        data=data,
        method=method,
        headers=supabase_headers(prefer_return=prefer_return),
    )

    try:
        with request.urlopen(req, timeout=15) as response:
            body = response.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase 요청 실패: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError("Supabase에 연결하지 못했습니다.") from exc


def supabase_get_leaderboard() -> List[Dict]:
    rows = supabase_request(
        "GET",
        "teams",
        params={
            "select": "id,name,color,score,completed_count",
            "order": "score.desc,completed_count.desc,id.asc",
        },
    )

    return [normalize_team_row(row) for row in rows or []]


def supabase_get_team_submissions(team_id: int) -> List[Dict]:
    rows = supabase_request(
        "GET",
        "submissions",
        params={
            "select": "quest_id",
            "team_id": f"eq.{team_id}",
        },
    )
    return rows or []


def supabase_submit_correct_answer(team_id: int, quest_id: str, points: int) -> int:
    result = supabase_request(
        "POST",
        "rpc/submit_team_quest",
        payload={
            "p_team_id": team_id,
            "p_quest_id": quest_id,
            "p_points": points,
        },
    )

    if not isinstance(result, list) or not result:
        raise RuntimeError("Supabase 함수 응답이 올바르지 않습니다.")

    row = result[0]
    return int(row.get("awarded_points", 0))


def supabase_reset_game() -> None:
    supabase_request(
        "DELETE",
        "submissions",
        params={"id": "gt.0"},
    )
    supabase_request(
        "PATCH",
        "teams",
        params={"id": "gt.0"},
        payload={"score": 0, "completed_count": 0},
    )


def normalize_team_row(row: Dict) -> Dict:
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "color": row["color"],
        "score": int(row.get("score", 0)),
        "completedCount": int(row.get("completed_count", row.get("completedCount", 0))),
    }
