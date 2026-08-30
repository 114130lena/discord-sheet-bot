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


# ==========================================
# Google Sheets ID
# ==========================================

SPREADSHEET_ID = "여기에_스프레드시트_ID"


def update_spreadsheet(project):

    spreadsheet = gc.open_by_key(
        SPREADSHEET_ID
    )

    worksheet = spreadsheet.sheet1

    # 기존 데이터 삭제
    worksheet.clear()

    # ==========================================
    # 제목
    # ==========================================

    worksheet.update(
        "A1:H1",
        [[
            "팀명",
            "약칭",
            "인원",
            "선수 1",
            "선수 2",
            "선수 3",
            "선수 4",
            "설명"
        ]]
    )

    rows = []

    for team in project.get("teams", []):

        roster_size = team.get(
            "roster_size",
            4
        )

        player4 = team.get(
            "player4",
            ""
        )

        # 3인 로스터
        if roster_size == 3:
            player4 = "—"

        rows.append([
            team.get(
                "team_name",
                ""
            ),

            team.get(
                "team_tag",
                ""
            ),

            f"{roster_size}인",

            team.get(
                "player1",
                ""
            ),

            team.get(
                "player2",
                ""
            ),

            team.get(
                "player3",
                ""
            ),

            player4,

            team.get(
                "description",
                ""
            )
        ])

    # ==========================================
    # 데이터 입력
    # ==========================================

    if rows:

        worksheet.update(
            f"A2:H{len(rows) + 1}",
            rows
        )

    # ==========================================
    # 열 너비
    # ==========================================

    widths = {
        "A": 180,
        "B": 80,
        "C": 70,
        "D": 120,
        "E": 120,
        "F": 120,
        "G": 120,
        "H": 400
    }

    for column, width in widths.items():

        worksheet.format(
            f"{column}:{column}",
            {
                "columnWidth": width
            }
        )

    # ==========================================
    # 헤더
    # ==========================================

    worksheet.format(
        "A1:H1",
        {
            "textFormat": {
                "bold": True,
                "fontSize": 11
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE"
        }
    )

    # ==========================================
    # 전체 데이터
    # ==========================================

    worksheet.format(
        f"A2:H{max(len(rows) + 1, 2)}",
        {
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP"
        }
    )

    # ==========================================
    # 팀명 / 약칭 / 인원 / 선수 가운데 정렬
    # ==========================================

    worksheet.format(
        f"A2:G{max(len(rows) + 1, 2)}",
        {
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP"
        }
    )

    # ==========================================
    # 설명 왼쪽 정렬
    # ==========================================

    worksheet.format(
        f"H2:H{max(len(rows) + 1, 2)}",
        {
            "horizontalAlignment": "LEFT",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP"
        }
    )

    # ==========================================
    # 헤더 고정
    # ==========================================

    worksheet.freeze(
        rows=1
    )

    # ==========================================
    # 필터
    # ==========================================

    try:

        worksheet.set_basic_filter()

    except Exception:

        pass

    # ==========================================
    # 행 높이
    # ==========================================

    if rows:

        worksheet.format(
            f"A2:H{len(rows) + 1}",
            {
                "wrapStrategy": "WRAP",
                "verticalAlignment": "MIDDLE"
            }
        )

    return spreadsheet.url
