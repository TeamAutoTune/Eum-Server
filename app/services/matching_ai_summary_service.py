from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.services.llm_service import (
    LLMAuthError,
    LLMConfigError,
    LLMExternalAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    chat,
)

logger = logging.getLogger(__name__)


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    text = str(value).strip()
    return [text] if text else []


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _join_korean_list(values: list[str], conjunction: str = "와") -> str:
    items = [str(item).strip() for item in values if str(item).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]}{conjunction} {items[1]}"
    return f"{', '.join(items[:-1])}{conjunction} {items[-1]}"


def _has_final_consonant(text: str) -> bool:
    value = _safe_text(text)
    if not value:
        return False
    last_char = value[-1]
    code = ord(last_char)
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    return False


def _attach_object_particle(text: str) -> str:
    value = _safe_text(text)
    if not value:
        return ""
    return f"{value}{'을' if _has_final_consonant(value) else '를'}"


def _attach_ro_particle(text: str) -> str:
    value = _safe_text(text)
    if not value:
        return ""
    return f"{value}{'으로' if _has_final_consonant(value) else '로'}"


def _map_style_label(value: Any) -> str:
    mapping = {
        "precise": "정교한 합주",
        "balanced": "균형 잡힌 합주",
        "expressive": "표현력 있는 합주",
    }
    text = _safe_text(value)
    return mapping.get(text, text)


def _map_region_label(value: Any) -> str:
    mapping = {
        "seoul": "서울",
        "gyeonggi": "경기",
        "incheon": "인천",
        "daejeon": "대전",
        "busan": "부산",
    }
    text = _safe_text(value)
    return mapping.get(text, text)


def _map_availability_label(value: Any) -> str:
    mapping = {
        "weekday_evening": "평일 저녁",
        "weekday_night": "평일 밤",
        "weekend_morning": "주말 오전",
        "weekend_day": "주말 낮",
        "weekend_afternoon": "주말 오후",
        "weekend_evening": "주말 저녁",
        "negotiable": "시간 협의",
    }
    text = _safe_text(value)
    return mapping.get(text, text)


def _map_practice_label(value: Any) -> str:
    mapping = {
        "weekly_1": "주 1회",
        "weekly_2": "주 1~2회",
        "weekly_3_plus": "주 3회 이상",
    }
    text = _safe_text(value)
    return mapping.get(text, text)


def _map_goal_label(value: Any) -> str:
    mapping = {
        "hobby": "취미 중심",
        "busking": "버스킹 지향",
        "band": "공연 지향",
        "pro": "프로 지향",
    }
    text = _safe_text(value)
    return mapping.get(text, text)


def _map_genre_label(value: Any) -> str:
    mapping = {
        "Rock": "록",
        "Indie": "인디",
        "Ballad": "발라드",
        "Jazz": "재즈",
        "R&B": "알앤비",
        "Metal": "메탈",
        "Pop": "팝",
        "HipHop": "힙합",
        "Hip-Hop": "힙합",
        "Funk": "펑크",
        "Electronic": "일렉트로닉",
    }
    text = _safe_text(value)
    return mapping.get(text, text)


def _map_instrument_label(value: Any) -> str:
    mapping = {
        "Vocal": "보컬",
        "Guitar": "기타",
        "Bass": "베이스",
        "Drums": "드럼",
        "Keyboard": "키보드",
        "Piano": "피아노",
        "Violin": "바이올린",
        "Saxophone": "색소폰",
        "Trumpet": "트럼펫",
        "DJ": "디제이",
    }
    text = _safe_text(value)
    if text in mapping:
        return mapping[text]
    lower = text.lower()
    if "vocal" in lower:
        return "보컬"
    if "guitar" in lower:
        return "기타"
    if "bass" in lower:
        return "베이스"
    if "drum" in lower:
        return "드럼"
    if "keyboard" in lower or "piano" in lower or "key" in lower:
        return "키보드"
    return text


def _map_role_noun(value: Any) -> str:
    mapping = {
        "Vocal": "보컬",
        "Guitar": "기타리스트",
        "Bass": "베이시스트",
        "Drums": "드러머",
        "Keyboard": "키보디스트",
        "Piano": "피아니스트",
        "Violin": "바이올리니스트",
        "Saxophone": "색소포니스트",
        "Trumpet": "트럼페터",
        "DJ": "디제이",
    }
    text = _safe_text(value)
    if text in mapping:
        return mapping[text]
    lower = text.lower()
    if "vocal" in lower:
        return "보컬"
    if "guitar" in lower:
        return "기타리스트"
    if "bass" in lower:
        return "베이시스트"
    if "drum" in lower:
        return "드러머"
    if "keyboard" in lower or "piano" in lower or "key" in lower:
        return "키보디스트"
    return text or "뮤지션"


def _extract_activity_goal_text(value: Any) -> str:
    if isinstance(value, dict):
        goals = _safe_list(value.get("activityGoals"))
        return ", ".join(goals)
    if isinstance(value, list):
        goals = _safe_list(value)
        return ", ".join(goals)
    return _safe_text(value)


def _extract_recruiting_parts(candidate: dict[str, Any]) -> list[str]:
    recruit_needs = candidate.get("recruitNeeds")
    if not isinstance(recruit_needs, list):
        return []

    parts: list[str] = []
    for item in recruit_needs:
        if not isinstance(item, dict):
            continue
        instrument = _safe_text(item.get("instrument"))
        part = _safe_text(item.get("part"))
        joined = " ".join([piece for piece in [instrument, part] if piece])
        if joined:
            parts.append(joined)
    return parts


def _profile_summary_payload(profile_data: dict[str, Any], candidate_data: dict[str, Any]) -> dict[str, Any]:
    merged = {**(profile_data or {}), **(candidate_data or {})}
    performance_preferences = merged.get("performancePreferences") if isinstance(merged.get("performancePreferences"), dict) else {}
    activity_goal = merged.get("activityGoal") if isinstance(merged.get("activityGoal"), dict) else {}

    payload = {
        "instruments": _safe_list(merged.get("instruments") or merged.get("playableInstruments")),
        "parts": _safe_list(merged.get("parts") or merged.get("primaryParts")),
        "genres": _safe_list(merged.get("genres") or merged.get("preferredGenres")),
        "style": _safe_text(merged.get("style") or performance_preferences.get("performanceStyle")),
        "region": _safe_text(merged.get("region") or performance_preferences.get("activityRegion")),
        "availability": _safe_list(merged.get("availability") or merged.get("availableTimes") or performance_preferences.get("availableTimeSlots")),
        "practiceFrequency": _safe_text(merged.get("practiceFrequency") or performance_preferences.get("practiceFrequency")),
        "activityGoal": _extract_activity_goal_text(activity_goal or merged.get("goals") or merged.get("activityGoals")),
    }
    return {key: value for key, value in payload.items() if value not in ("", [], None)}


def _team_recruit_summary_payload(profile_data: dict[str, Any], recruit_needs: list[dict[str, Any]]) -> dict[str, Any]:
    team_profile = profile_data.get("teamProfile") if isinstance(profile_data.get("teamProfile"), dict) else {}
    merged = {**(profile_data or {}), **team_profile}
    activity_goal = merged.get("activityGoal") if isinstance(merged.get("activityGoal"), dict) else {}

    payload = {
        "teamName": _safe_text(merged.get("teamName")),
        "genres": _safe_list(merged.get("genres")),
        "region": _safe_text(merged.get("region")),
        "practiceFrequency": _safe_text(merged.get("practiceFrequency")),
        "activityGoal": _extract_activity_goal_text(activity_goal or merged.get("goals") or merged.get("activityGoals")),
        "recruitNeeds": _extract_recruiting_parts({"recruitNeeds": recruit_needs}),
    }
    return {key: value for key, value in payload.items() if value not in ("", [], None)}


def _has_summary_material(payload: dict[str, Any]) -> bool:
    return any(payload.values())


def _build_prompt(payload: dict[str, Any], *, subject: str) -> str:
    example = (
        "\"인디와 록을 선호하며 주 1~2회 합주를 원하는 공연 지향 보컬입니다.\""
        if subject == "개인 프로필"
        else "\"홍대 인근에서 활동하며 주 1회 합주하는 인디 밴드로, 현재 드러머를 모집 중입니다.\""
    )
    return (
        f"아래 {subject} JSON 데이터만 사용해서 소개 한 줄을 작성해 주세요.\n"
        "규칙:\n"
        "1) 반말 금지, 존댓말 1문장\n"
        "2) 길이 45~80자 내외\n"
        "3) 키워드 나열 금지, 자연스러운 한국어 문장으로 작성\n"
        "4) 입력 데이터에 없는 사실 추측 금지\n"
        "5) 가능하면 장르/활동 방식/합주 빈도/포지션(또는 모집 포지션)을 문장에 녹여서 작성\n"
        "6) 과장/광고 문구 금지\n"
        "7) 결과는 문장 하나만 출력\n\n"
        f"문체 예시:\n{example}\n\n"
        f"입력 JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _normalize_summary(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text.strip()).strip("\"' ")
    if not normalized:
        return None

    if "\n" in normalized:
        normalized = normalized.splitlines()[0].strip()

    normalized = normalized.rstrip(".!? ")
    if not normalized:
        return None

    if not normalized.endswith("입니다") and not normalized.endswith("입니다요"):
        if normalized.endswith("다"):
            normalized = f"{normalized[:-1]}입니다"
        else:
            normalized = f"{normalized}입니다"

    normalized = f"{normalized}."

    if len(normalized) > 120:
        normalized = normalized[:120].rstrip(" .") + "."

    return normalized


def _fallback_profile_summary(payload: dict[str, Any]) -> str | None:
    instruments = _safe_list(payload.get("instruments"))[:2]
    genres = [_map_genre_label(item) for item in _safe_list(payload.get("genres"))[:2]]
    region = _map_region_label(payload.get("region"))
    practice = _map_practice_label(payload.get("practiceFrequency"))
    goal = _join_korean_list(
        [_map_goal_label(item) for item in _safe_list(payload.get("activityGoal")) or _safe_text(payload.get("activityGoal")).split(",")],
        conjunction="와",
    )
    availability = _join_korean_list(
        [_map_availability_label(item) for item in _safe_list(payload.get("availability"))[:2]],
        conjunction="와",
    )
    style = _map_style_label(payload.get("style"))
    instrument_text = _join_korean_list([_map_instrument_label(item) for item in instruments], conjunction="와")
    role_text = _map_role_noun(instruments[0]) if instruments else "뮤지션"
    genre_text = _join_korean_list(genres, conjunction="와")

    clauses: list[str] = []
    if genre_text:
        clauses.append(f"{_attach_object_particle(genre_text)} 선호하며")
    if region:
        clauses.append(f"{region}에서 활동하고")
    if practice:
        clauses.append(f"{practice} 합주를 선호하는")
    elif availability:
        clauses.append(f"{availability} 위주로 활동하는")
    if goal:
        clauses.append(f"{goal} {role_text}")
    elif instrument_text:
        clauses.append(f"{instrument_text}를 맡는 {role_text}")
    if style:
        clauses.append(f"스타일은 {style}인")

    sentence = " ".join(clauses).strip()
    if not sentence:
        return None
    if not sentence.endswith(("보컬", "기타리스트", "드러머", "베이시스트", "키보디스트", "피아니스트", "뮤지션", "디제이")):
        sentence = f"{sentence}입니다"
    return _normalize_summary(sentence)


def _fallback_team_summary(payload: dict[str, Any]) -> str | None:
    team_name = _safe_text(payload.get("teamName"))
    genres = _join_korean_list(
        [_map_genre_label(item) for item in _safe_list(payload.get("genres"))[:2]],
        conjunction="와",
    )
    region = _map_region_label(payload.get("region"))
    practice = _map_practice_label(payload.get("practiceFrequency"))
    goal = _join_korean_list(
        [_map_goal_label(item) for item in _safe_list(payload.get("activityGoal")) or _safe_text(payload.get("activityGoal")).split(",")],
        conjunction="와",
    )
    needs = _join_korean_list(
        [_map_role_noun(item) for item in _safe_list(payload.get("recruitNeeds"))[:2]],
        conjunction="와",
    )

    intro_parts: list[str] = []
    if region:
        intro_parts.append(f"{region} 인근에서 활동하며")
    if practice:
        intro_parts.append(f"{practice} 합주하는")

    team_descriptor = ""
    if goal and genres:
        team_descriptor = f"{goal} {genres} 팀"
    elif genres:
        team_descriptor = f"{genres} 팀"
    elif goal:
        team_descriptor = f"{goal} 팀"
    elif team_name:
        team_descriptor = f"{team_name} 팀"

    if team_descriptor:
        intro_parts.append(team_descriptor)

    sentence = " ".join(intro_parts).strip()
    if needs:
        sentence = f"{_attach_ro_particle(sentence)}, 현재 {needs}를 모집 중".strip()
    if not sentence:
        return None
    return _normalize_summary(sentence)


def _generate_summary(prompt: str) -> str | None:
    gemini_api_key = (settings.gemini_api_key or "").strip()
    llm_api_key = (settings.llm_api_key or "").strip()
    has_any_llm_key = bool(llm_api_key or gemini_api_key)

    if not gemini_api_key:
        logger.info("summary generation: GEMINI_API_KEY is not configured")

    try:
        if has_any_llm_key:
            answer = chat(prompt)
            summary = _normalize_summary(answer)
            if not summary:
                logger.warning("summary generation failed: empty normalized response")
            return summary

        logger.info("summary generation skipped: no server LLM API key is configured")
        return None
    except LLMConfigError:
        logger.info("summary generation skipped: llm_api_key is not configured")
        return None
    except LLMAuthError:
        logger.warning("summary generation failed: provider auth error")
        return None
    except LLMRateLimitError:
        logger.warning("summary generation failed: provider rate limited")
        return None
    except LLMTimeoutError:
        logger.warning("summary generation failed: provider timeout")
        return None
    except LLMExternalAPIError:
        logger.warning("summary generation failed: external provider error")
        return None
    except Exception:
        logger.exception("summary generation failed: unexpected error")
        return None


def generate_profile_summary(*, profile_data: dict[str, Any], candidate_data: dict[str, Any]) -> str | None:
    payload = _profile_summary_payload(profile_data=profile_data or {}, candidate_data=candidate_data or {})
    if not _has_summary_material(payload):
        return None

    llm_summary = _generate_summary(_build_prompt(payload, subject="개인 프로필"))
    if llm_summary:
        return llm_summary
    return _fallback_profile_summary(payload)


def generate_team_recruit_summary(*, profile_data: dict[str, Any], recruit_needs: list[dict[str, Any]]) -> str | None:
    payload = _team_recruit_summary_payload(profile_data=profile_data or {}, recruit_needs=recruit_needs or [])
    if not _has_summary_material(payload):
        return None

    llm_summary = _generate_summary(_build_prompt(payload, subject="팀 구인"))
    if llm_summary:
        return llm_summary
    return _fallback_team_summary(payload)
