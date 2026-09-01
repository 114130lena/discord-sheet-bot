import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않아!")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3.5-flash-lite"

PROMPT = r'''
너는 이터널리턴 대회 로스터 표에서 데이터를 추출하는 AI다.
여러 이미지가 들어오면 같은 표의 이어지는 부분일 수 있으므로 전체 이미지를 함께 보고 중복 팀은 합치되, 서로 다른 팀은 모두 추출한다.

반드시 추출할 것:
- team_name: 팀의 정식 팀명. 이미지에 실제로 적힌 값만.
- team_tag: 팀의 약칭/태그. team_name과 분리해서 읽는다. 약칭이 없으면 "".
- player1~player4: 실제 선수 이름. 이미지에 보이는 순서를 유지한다.
- roster_size: 실제 선수 수. 3명 또는 4명.

절대로 추측하지 말 것:
- 실험체
- 전략
- 교전 포인트
- 대회명/날짜/순위 등을 팀명으로 오인
- 보이지 않는 약칭이나 선수명 생성

실험체와 전략 관련 필드는 항상 빈 문자열.
3인 로스터면 player4도 빈 문자열.
코치/감독/매니저/스태프는 선수로 넣지 않는다.
읽을 수 없는 선수명은 "[확인 필요]".

반드시 JSON만 출력한다.
{
  "teams": [
    {
      "team_name": "",
      "team_tag": "",
      "roster_size": 3,
      "player1": "",
      "player2": "",
      "player3": "",
      "player4": "",
      "experiment1": "",
      "experiment2": "",
      "experiment3": "",
      "experiment4": "",
      "strategy": "",
      "combat_points": "",
      "notes": ""
    }
  ]
}
'''

CLEANUP_PROMPT = r'''
너는 방금 이터널리턴 대회 로스터 이미지에서 추출된 텍스트를 검수하는 AI다.
원본 이미지를 다시 자세히 보고, 아래의 추출 결과에서 OCR/판독 실수로 보이는 오타만 매우 보수적으로 수정해라.

중요 규칙:
- 원본 이미지의 글자 모양으로 확실히 확인되는 경우에만 수정한다.
- 선수명이나 팀명을 추측해서 새로운 이름을 만들어내지 않는다.
- 한글 자모, 영문 대소문자, 숫자 1/I/l, 0/O, 붙어 읽힌 문자 등 명백한 판독 오류는 원본을 보고 수정할 수 있다.
- 확신이 없으면 기존 값을 그대로 유지한다.
- 팀명, 팀 태그, player1~player4만 검수한다.
- 선수 순서와 팀 순서는 절대로 바꾸지 않는다.
- 새 팀이나 새 선수를 추가하거나 삭제하지 않는다.

아래 추출 결과와 같은 구조의 JSON만 출력한다.
추출 결과:
'''


def _clean_json(text):
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _normalize(result):
    teams = result.get("teams", []) if isinstance(result, dict) else []
    normalized = []
    seen = set()
    for raw in teams:
        team = dict(raw or {})
        name = str(team.get("team_name", "")).strip()
        tag = str(team.get("team_tag", "")).strip()
        try:
            size = int(team.get("roster_size", 4))
        except Exception:
            size = 4
        players = [str(team.get(f"player{i}", "")).strip() for i in range(1, 5)]
        actual = [p for p in players if p]
        if size not in (3, 4):
            size = 3 if len(actual) == 3 else 4
        if size == 3:
            players[3] = ""
        key = (name.lower(), tag.lower(), tuple(p.lower() for p in players if p))
        if key in seen:
            continue
        seen.add(key)
        normalized.append({
            "team_name": name,
            "team_tag": tag,
            "roster_size": size,
            "player1": players[0],
            "player2": players[1],
            "player3": players[2],
            "player4": players[3],
            "experiment1": "",
            "experiment2": "",
            "experiment3": "",
            "experiment4": "",
            "strategy": "",
            "combat_points": "",
            "notes": ""
        })
    return {"teams": normalized}


def _cleanup_extraction(images, extracted):
    """Re-check extracted names against the original images.

    This deliberately makes no corrections unless the model can visually verify
    an obvious OCR/reading mistake, so uncertain names stay unchanged.
    """
    contents = []
    for image_data, mime_type in images:
        contents.append(types.Part.from_bytes(data=image_data, mime_type=mime_type))
    contents.append(CLEANUP_PROMPT + "\n" + json.dumps(extracted, ensure_ascii=False))
    response = client.models.generate_content(model=MODEL, contents=contents)
    cleaned = json.loads(_clean_json(response.text))
    if not isinstance(cleaned, dict) or not isinstance(cleaned.get("teams"), list):
        return extracted
    return cleaned


def analyze_images(images):
    contents = []
    for image_data, mime_type in images:
        contents.append(types.Part.from_bytes(data=image_data, mime_type=mime_type))
    contents.append(PROMPT)
    response = client.models.generate_content(model=MODEL, contents=contents)
    extracted = json.loads(_clean_json(response.text))

    # Second visual pass: fixes only clearly verifiable reading/OCR mistakes.
    try:
        extracted = _cleanup_extraction(images, extracted)
    except Exception as e:
        # A failed cleanup must never discard a successful first analysis.
        print(f"OCR 검수 단계 건너뜀: {type(e).__name__}: {e}")

    return _normalize(extracted)


def analyze_image(image_data, mime_type):
    return analyze_images([(image_data, mime_type)])