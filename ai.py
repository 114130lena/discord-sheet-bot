import os
import base64
import json

from dotenv import load_dotenv
from google import genai


load_dotenv()


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def analyze_image(
    image_data,
    mime_type
):

    prompt = """
이 이미지는 대회 팀 명단 표다.

이미지에 있는 모든 팀을 찾아서 정보를 추출해라.

각 팀에서 다음 정보를 추출한다.

- team_name
- roster_size
- player1
- player2
- player3
- player4
- description


[로스터 인원 판별 규칙]

1. 이미지에서 해당 팀에 실제로 등록된 선수의 수를 센다.
2. 실제 선수가 3명이면 roster_size는 3이다.
3. 실제 선수가 4명이면 roster_size는 4이다.
4. 3인 로스터의 player4는 반드시 빈 문자열("")로 한다.
5. 없는 선수를 절대로 추측해서 추가하지 않는다.
6. 선수 이름을 읽을 수 없는 것과 선수가 존재하지 않는 것은 구분한다.
7. 명단에 선수 3명만 존재한다면 3인 로스터로 판단한다.
8. roster_size는 반드시 숫자 3 또는 4만 사용한다.
9. 예비 선수, 코치, 매니저 등은 선수로 세지 않는다.
10. 실제 경기 로스터에 등록된 선수만 player1~player4에 넣는다.

읽을 수 없는 선수 이름은 "[확인 필요]"라고 표시한다.

반드시 JSON만 출력한다.

형식:

{
  "teams": [
    {
      "team_name": "팀명",
      "roster_size": 3,
      "player1": "선수1",
      "player2": "선수2",
      "player3": "선수3",
      "player4": "",
      "description": "설명"
    }
  ]
}

이미지에 존재하는 모든 팀을 출력한다.
"""

    encoded = base64.b64encode(
        image_data
    ).decode("utf-8")

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[
            prompt,
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": encoded
                }
            }
        ]
    )

    text = response.text.strip()

    if text.startswith("```"):

        text = text.replace(
            "```json",
            ""
        )

        text = text.replace(
            "```",
            ""
        )

        text = text.strip()

    result = json.loads(text)

    for team in result.get(
        "teams",
        []
    ):

        if team.get(
            "roster_size"
        ) not in [3, 4]:

            team["roster_size"] = 4

        if team["roster_size"] == 3:

            team["player4"] = ""

        for key in [
            "team_name",
            "player1",
            "player2",
            "player3",
            "player4",
            "description"
        ]:

            if key not in team:

                team[key] = ""

    return result
