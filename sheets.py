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


def create_spreadsheet(project):

    spreadsheet_name = "전력분석"

    spreadsheet = gc.create(
        spreadsheet_name
    )

    worksheet = spreadsheet.sheet1

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
