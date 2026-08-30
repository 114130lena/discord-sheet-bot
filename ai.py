import os
import base64
import json

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def analyze_image(image_data, mime_type):
    prompt = """
이 이미지는 대회 팀 명단 표다.

이미지에 있는 모든 팀을 분석해라.

각 팀에서 다음 정보를 추출한다.

- team_name
- player1
- player2
- player3
- player4
- description

절대로 이미지에 없는 내용을 추측하지 마라.

읽을 수 없는 내용은 "[확인 필요]"로 표시한다.

반드시 JSON만 출력한다.

형식:

{
  "teams": [
    {
      "team_name": "팀명",
      "player1": "선수1",
      "player2": "선수2",
      "player3": "선수3",
      "player4": "선수4",
      "description": "설명"
    }
  ]
}
"""

    encoded = base64.b64encode(image_data).decode("utf-8")

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

    # 혹시 ```json 형태로 오는 경우 제거
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)
