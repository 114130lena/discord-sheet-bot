import gspread
from google.oauth2.service_account import Credentials


# Google Sheets / Drive 권한
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


# 서비스 계정 인증
credentials = Credentials.from_service_account_file(
    "google-service-account.json",
    scopes=SCOPES
)

gc = gspread.authorize(credentials)


def create_spreadsheet(project):
    """
    프로젝트 데이터를 새로운 Google 스프레드시트로 만든다.
    """

    spreadsheet_name = "전력분석"

    spreadsheet = gc.create(spreadsheet_name)

    worksheet = spreadsheet.sheet1

    # 헤더
    headers = [
        "팀명",
        "로스터",
        "선수 1",
        "선수 2",
        "선수 3",
        "선수 4",
        "설명"
    ]

    worksheet.append_row(headers)

    # 팀 데이터
    for team in project.get("teams", []):

        roster_size = team.get(
            "roster_size",
            4
        )

        player4 = team.get(
            "player4",
            ""
        )

        # 3인 로스터면 선수4 비우기
        if roster_size == 3:
            player4 = ""

        row = [
            team.get("team_name", ""),
            f"{roster_size}인",
            team.get("player1", ""),
            team.get("player2", ""),
            team.get("player3", ""),
            player4,
            team.get("description", "")
        ]

        worksheet.append_row(row)

    # 헤더 고정
    worksheet.freeze(rows=1)

    # 필터
    worksheet.set_basic_filter()

    # 열 너비
    worksheet.format(
        "A:G",
        {
            "wrapStrategy": "WRAP",
            "verticalAlignment": "MIDDLE"
        }
    )

    # 헤더 굵게
    worksheet.format(
        "A1:G1",
        {
            "textFormat": {
                "bold": True
            }
        }
    )

    return spreadsheet.url
