import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


credentials = Credentials.from_service_account_file(
    "google-service-account.json",
    scopes=SCOPES
)

gc = gspread.authorize(credentials)


# 여기에 네 Google Sheets ID를 넣어
SPREADSHEET_ID = "여기에_스프레드시트_ID"


def update_spreadsheet(project):

    spreadsheet = gc.open_by_key(
        SPREADSHEET_ID
    )

    worksheet = spreadsheet.sheet1

    # 기존 데이터 삭제
    worksheet.clear()

    headers = [
        "팀명",
        "로스터",
        "선수 1",
        "선수 2",
        "선수 3",
        "선수 4",
        "설명"
    ]

    rows = [headers]

    for team in project.get("teams", []):

        roster_size = team.get(
            "roster_size",
            4
        )

        player4 = team.get(
            "player4",
            ""
        )

        if roster_size == 3:
            player4 = ""

        rows.append([
            team.get("team_name", ""),
            f"{roster_size}인",
            team.get("player1", ""),
            team.get("player2", ""),
            team.get("player3", ""),
            player4,
            team.get("description", "")
        ])

    worksheet.update(
        "A1",
        rows
    )

    worksheet.freeze(rows=1)

    worksheet.set_basic_filter()

    worksheet.format(
        "A:G",
        {
            "wrapStrategy": "WRAP",
            "verticalAlignment": "MIDDLE"
        }
    )

    worksheet.format(
        "A1:G1",
        {
            "textFormat": {
                "bold": True
            }
        }
    )

    return spreadsheet.url
