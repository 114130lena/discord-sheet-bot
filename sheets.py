import gspread
from google.oauth2.service_account import Credentials


# =========================================================
# Google API 설정
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_file(
    "google-service-account.json",
    scopes=SCOPES
)

gc = gspread.authorize(credentials)


# =========================================================
# Spreadsheet
# =========================================================

SPREADSHEET_ID = "1FARr4g1gNM1P9oaFvpFSd3xWJo1BtgBy9398WwlzU8M"


# =========================================================
# Worksheet 가져오기 / 없으면 생성
# =========================================================

def get_or_create_worksheet(
    spreadsheet,
    title,
    rows=200,
    cols=12
):

    try:
        return spreadsheet.worksheet(title)

    except gspread.WorksheetNotFound:

        return spreadsheet.add_worksheet(
            title=title,
            rows=rows,
            cols=cols
        )


# =========================================================
# 전력분석 시트
# =========================================================

def update_spreadsheet(project):

    spreadsheet = gc.open_by_key(
        SPREADSHEET_ID
    )

    worksheet = get_or_create_worksheet(
        spreadsheet,
        "전력분석",
        rows=200,
        cols=12
    )

    # =====================================================
    # 기존 내용 삭제
    # =====================================================

    worksheet.clear()

    # =====================================================
    # 기존 병합 제거
    # =====================================================

    try:
        worksheet.batch_update({
            "requests": [
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 0,
                            "endRowIndex": 200,
                            "startColumnIndex": 0,
                            "endColumnIndex": 12
                        }
                    }
                }
            ]
        })

    except Exception:
        pass

    teams = project.get(
        "teams",
        []
    )

    # =====================================================
    # 제목
    # =====================================================

    worksheet.merge_cells("A1:I1")

    worksheet.update(
        range_name="A1",
        values=[
            ["2026 전력분석"]
        ]
    )

    worksheet.format(
        "A1:I1",
        {
            "textFormat": {
                "bold": True,
                "fontSize": 16
            },
            "horizontalAlignment": "LEFT",
            "verticalAlignment": "MIDDLE"
        }
    )

    # =====================================================
    # 헤더
    # =====================================================

    headers = [
        "팀",
        "선수",
        "실험체",
        "운영 전략 / 교전 포인트"
    ]

    worksheet.update(
        range_name="A2:D2",
        values=[headers]
    )

    worksheet.update(
        range_name="F2:I2",
        values=[headers]
    )

    header_format = {
        "textFormat": {
            "bold": True,
            "fontSize": 11
        },
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "WRAP"
    }

    worksheet.format(
        "A2:D2",
        header_format
    )

    worksheet.format(
        "F2:I2",
        header_format
    )

    # =====================================================
    # 팀 작성
    # =====================================================

    def write_team(
        team,
        start_row,
        team_column,
        player_column,
        experiment_column,
        analysis_column
    ):

        team_name = team.get(
            "team_name",
            ""
        )

        team_tag = team.get(
            "team_tag",
            ""
        )

        # ---------------------------------------------
        # 팀명 / 약칭
        # ---------------------------------------------

        if team_name and team_tag:

            display_name = (
                f"{team_name}\n"
                f"[{team_tag}]"
            )

        elif team_name:

            display_name = team_name

        elif team_tag:

            display_name = f"[{team_tag}]"

        else:

            display_name = ""

        # ---------------------------------------------
        # 로스터
        # ---------------------------------------------

        try:

            roster_size = int(
                team.get(
                    "roster_size",
                    4
                )
            )

        except:

            roster_size = 4

        players = [
            team.get("player1", ""),
            team.get("player2", ""),
            team.get("player3", ""),
            team.get("player4", "")
        ]

        # 3인 로스터
        if roster_size == 3:
            players[3] = ""

        # ---------------------------------------------
        # 팀명 영역
        # ---------------------------------------------

        end_row = start_row + 3

        worksheet.merge_cells(
            f"{team_column}{start_row}:"
            f"{team_column}{end_row}"
        )

        worksheet.update(
            range_name=f"{team_column}{start_row}",
            values=[
                [display_name]
            ]
        )

        # ---------------------------------------------
        # 선수 영역
        # ---------------------------------------------

        for i in range(4):

            row = start_row + i

            player = players[i]

            # 실험체는 항상 빈칸
            experiment = ""

            # 분석 역시 현재 빈칸
            analysis = ""

            worksheet.update(
                range_name=(
                    f"{player_column}{row}:"
                    f"{analysis_column}{row}"
                ),
                values=[
                    [
                        player,
                        experiment,
                        analysis
                    ]
                ]
            )

        # ---------------------------------------------
        # 팀명 서식
        # ---------------------------------------------

        worksheet.format(
            f"{team_column}{start_row}:"
            f"{team_column}{end_row}",
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

        # ---------------------------------------------
        # 선수 / 실험체
        # ---------------------------------------------

        worksheet.format(
            f"{player_column}{start_row}:"
            f"{experiment_column}{end_row}",
            {
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP"
            }
        )

        # ---------------------------------------------
        # 분석
        # ---------------------------------------------

        worksheet.format(
            f"{analysis_column}{start_row}:"
            f"{analysis_column}{end_row}",
            {
                "horizontalAlignment": "LEFT",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP"
            }
        )

    # =====================================================
    # 좌 / 우 배치
    # =====================================================

    left_teams = teams[0::2]
    right_teams = teams[1::2]

    # =====================================================
    # 왼쪽 팀
    # =====================================================

    current_row = 3

    for team in left_teams:

        write_team(
            team,
            current_row,
            "A",
            "B",
            "C",
            "D"
        )

        current_row += 4

    # =====================================================
    # 오른쪽 팀
    # =====================================================

    current_row = 3

    for team in right_teams:

        write_team(
            team,
            current_row,
            "F",
            "G",
            "H",
            "I"
        )

        current_row += 4

    # =====================================================
    # 열 너비
    # =====================================================

    column_widths = {
        "A": 170,
        "B": 120,
        "C": 110,
        "D": 320,

        "E": 25,

        "F": 170,
        "G": 120,
        "H": 110,
        "I": 320
    }

    for column, width in column_widths.items():

        worksheet.format(
            f"{column}:{column}",
            {
                "columnWidth": width
            }
        )

    # =====================================================
    # 테두리
    # =====================================================

    last_row = max(
        current_row,
        7
    )

    border_format = {
        "borders": {
            "top": {
                "style": "SOLID"
            },
            "bottom": {
                "style": "SOLID"
            },
            "left": {
                "style": "SOLID"
            },
            "right": {
                "style": "SOLID"
            },
            "innerHorizontal": {
                "style": "SOLID"
            },
            "innerVertical": {
                "style": "SOLID"
            }
        }
    }

    worksheet.format(
        f"A2:D{last_row}",
        border_format
    )

    worksheet.format(
        f"F2:I{last_row}",
        border_format
    )

    # =====================================================
    # 헤더 고정
    # =====================================================

    worksheet.freeze(
        rows=2
    )

    print(
        f"Google Sheets 업데이트 완료: "
        f"{len(teams)}개 팀"
    )

    return spreadsheet.url
