from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def build_payload(mode: str = "apply") -> dict:
    payload = {
        "profile": {
            "instruments": ["guitar"],
            "parts": ["lead"],
            "genres": ["rock", "indie", "pop"],
            "availability": ["weekday_evening", "weekend_day", "weekend_evening"],
            "region": "서울특별시 강남구",
            "practiceFrequency": "weekly_1",
            "activityGoal": {"activityGoals": ["band"]},
            "requiredConditions": [],
            "avoidConditions": [],
        },
        "mode": mode,
        "min_score": 0,
        "limit": 20,
        "hard_filters": {"same_instrument": False, "same_region": False},
        "recruit_needs": [],
    }
    if mode == "recruit":
        payload["recruit_needs"] = [
            {"instrument": "guitar", "part": "lead", "count": 1, "required": False}
        ]
    return payload


def main() -> None:
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"user_id": "seed_test_001", "password": "seed1234"})
    print("login_status:", login.status_code)
    if login.status_code != 200:
        print("login_body:", login.text)
        return

    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for mode in ("apply", "recruit"):
        resp = client.post("/api/matching/match", json=build_payload(mode), headers=headers)
        print(f"{mode}_status:", resp.status_code)
        if resp.status_code != 200:
            print(f"{mode}_body:", resp.text)
            continue

        body = resp.json()
        top3 = [
            {"id": row.get("id"), "score": row.get("matchScore")}
            for row in body.get("results", [])[:3]
        ]
        print(f"{mode}_ranking_version:", body.get("ranking_version"))
        print(f"{mode}_results_count:", len(body.get("results", [])))
        print(f"{mode}_top3:", top3)


if __name__ == "__main__":
    main()
