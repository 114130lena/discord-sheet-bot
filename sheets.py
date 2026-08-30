import gspread
from google.oauth2.service_account import Credentials


# ==========================================
# Google API 설정
# ==========================================

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
# Google Sheets
# ==========================================

SPREADSHEET_ID = "1FARr4g1gNM1P9oaFvpFSd3xWJo1BtgBy9398WwlzU8M"


# ==========================================
# 스프레드시트 업데이트
# ==========================================

def update_spreadsheet(project):

    spreadsheet = gc.open_by_key(
        SPREADSHEET_ID
    )

    worksheet = spreadsheet.sheet1

    # 기존 데이터 전체 삭제
    worksheet.clear()

    # ==========================================
    # 헤더
    # ==========================================

    headers = [
        "팀명",
        "약칭",
        "인원",
        "선수 1",
        "선수 2",
        "선수 3",
        "선수 4",
        "설명"
    ]

    worksheet.update(
        "A1:H1",
        [headers]
    )

    # ==========================================
    # 데이터 생성
    # ==========================================

    rows = []

    for team in project.get("teams", []):

        roster_size = team.get(
            "roster_size",
            4
        )

        # 숫자로 변환
        try:
            roster_size = int(roster_size)
        except:
            roster_size = 4

        # 3인 로스터면 선수 4는 표시하지 않음
        if roster_size == 3:
            player4 = "—"
        else:
            player4 = team.get(
                "player4",
                ""
            )

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
    # 열 너비 설정
    # ==========================================

    column_widths = {
        "A": 180,   # 팀명
        "B": 80,    # 약칭
        "C": 70,    # 인원
        "D": 120,   # 선수 1
        "E": 120,   # 선수 2
        "F": 120,   # 선수 3
        "G": 120,   # 선수 4
        "H": 400    # 설명
    }

    for column, width in column_widths.items():

        worksheet.format(
            f"{column}:{column}",
            {
                "columnWidth": width
            }
        )

    # ==========================================
    # 헤더 서식
    # ==========================================

    worksheet.format(
        "A1:H1",
        {
            "textFormat": {
                "bold": True,
                "fontSize": 11
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP"
        }
    )

    # ==========================================
    # 전체 데이터 서식
    # ==========================================

    last_row = max(
        len(rows) + 1,
        2
    )

    worksheet.format(
        f"A2:H{last_row}",
        {
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP"
        }
    )

    # ==========================================
    # 팀명 / 약칭 / 인원 / 선수
    # 가운데 정렬
    # ==========================================

    worksheet.format(
        f"A2:G{last_row}",
        {
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP"
        }
    )

    # ==========================================
    # 설명
    # ==========================================

    worksheet.format(
        f"H2:H{last_row}",
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

    except Exception as e:

        print(
            f"필터 설정 실패: {e}"
        )

    # ==========================================
    # 행 높이
    # ==========================================

    if rows:

        worksheet.format(
            f"A2:H{last_row}",
            {
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
                "textFormat": {
                    "fontSize": 10
                }
            }
        )

    print(
        f"Google Sheets 업데이트 완료: "
        f"{len(rows)}개 팀"
    )

    return spreadsheet.url
