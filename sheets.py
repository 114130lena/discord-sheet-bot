import gspread

from google.oauth2.service_account import Credentials


# =========================================================
# Google API
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

SPREADSHEET_ID = (
    "1FARr4g1gNM1P9oaFvpFSd3xWJo1BtgBy9398WwlzU8M"
)


# =========================================================
# 메인 전력분석 시트
# =========================================================

def get_or_create_worksheet(
    spreadsheet,
    title,
    rows=100,
    cols=20
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
# 메인 시트 생성
# =========================================================

def update_spreadsheet(project):

    spreadsheet = gc.open_by_key(
        SPREADSHEET_ID
    )

    # -----------------------------------------------------
    # 전력분석 시트
    # -----------------------------------------------------

    worksheet = get_or_create_worksheet(
        spreadsheet,
        "전력분석",
        rows=200,
        cols=12
    )

    # 기존 내용 제거
    worksheet.clear()

    # 기존 병합 제거
    try:

        worksheet.unmerge_cells(
            "A1:L200"
        )

    except Exception:

        pass

    teams = project.get(
        "teams",
        []
    )

    # =====================================================
    # 제목
    # =====================================================

    worksheet.merge_cells(
        "A1:H1"
    )

    worksheet.update(
        "A1",
        "2026 전력분석"
    )

    worksheet.format(
        "A1:H1",
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

    # 왼쪽 / 오른쪽 두 영역
    worksheet.update(
        "A2:D2",
        [headers]
    )

    worksheet.update(
        "F2:I2",
        [headers]
    )

    # 헤더 서식
    for header_range in [
        "A2:D2",
        "F2:I2"
    ]:

        worksheet.format(
            header_range,
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

    # =====================================================
    # 팀을 좌우 2열로 배치
    # =====================================================

    left_teams = teams[0::2]
    right_teams = teams[1::2]

    # -----------------------------------------------------
    # 팀 하나를 작성하는 함수
    # -----------------------------------------------------

    def write_team(
        ws,
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

        # 팀명 + 약칭 표시
        if team_tag:

            display_name = (
                f"{team_name}\n"
                f"[{team_tag}]"
            )

        else:

            display_name = team_name

        # -------------------------------------------------
        # 선수
        # -------------------------------------------------

        players = [
            team.get("player1", ""),
            team.get("player2", ""),
            team.get("player3", ""),
            team.get("player4", "")
        ]

        # 실제 로스터 수
        try:

            roster_size = int(
                team.get(
                    "roster_size",
                    4
                )
            )

        except:

            roster_size = 4

        if roster_size == 3:

            players[3] = ""

        # -------------------------------------------------
        # 팀 영역
        # -------------------------------------------------

        end_row = start_row + 3

        # 팀명은 4줄 병합
        ws.merge_cells(
            f"{team_column}{start_row}:"
            f"{team_column}{end_row}"
        )

        ws.update(
            f"{team_column}{start_row}",
            display_name
        )

        # -------------------------------------------------
        # 선수 / 실험체 / 분석
        # -------------------------------------------------

        for index in range(4):

            row = start_row + index

            player = players[index]

            # 실험체는 항상 빈칸
            experiment = ""

            # 분석도 현재는 빈칸
            analysis = ""

            ws.update(
                f"{player_column}{row}:"
                f"{analysis_column}{row}",
                [[
                    player,
                    experiment,
                    analysis
                ]]
            )

        # -------------------------------------------------
        # 팀 영역 서식
        # -------------------------------------------------

        ws.format(
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

        # -------------------------------------------------
        # 선수 / 실험체
        # -------------------------------------------------

        ws.format(
            f"{player_column}{start_row}:"
            f"{experiment_column}{end_row}",
            {
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP"
            }
        )

        # -------------------------------------------------
        # 분석
        # -------------------------------------------------

        ws.format(
            f"{analysis_column}{start_row}:"
            f"{analysis_column}{end_row}",
            {
                "horizontalAlignment": "LEFT",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP"
            }
        )

        # -------------------------------------------------
        # 행 높이
        # -------------------------------------------------

        for row in range(
            start_row,
            end_row + 1
        ):

            ws.format(
                f"{row}:{row}",
                {
                    "rowHeight": 32
                }
            )

    # =====================================================
    # 왼쪽 팀
    # =====================================================

    current_row = 3

    for team in left_teams:

        write_team(
            worksheet,
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
            worksheet,
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

    widths = {
        "A": 150,
        "B": 120,
        "C": 110,
        "D": 330,

        "E": 25,

        "F": 150,
        "G": 120,
        "H": 110,
        "I": 330
    }

    for column, width in widths.items():

        worksheet.format(
            f"{column}:{column}",
            {
                "columnWidth": width
            }
        )

    # =====================================================
    # 전체 테두리
    # =====================================================

    last_row = max(
        current_row,
        7
    )

    for cell_range in [
        f"A2:D{last_row}",
        f"F2:I{last_row}"
    ]:

        worksheet.format(
            cell_range,
            {
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
        )

    # =====================================================
    # 제목 행 높이
    # =====================================================

    worksheet.format(
        "1:1",
        {
            "rowHeight": 35
        }
    )

    worksheet.format(
        "2:2",
        {
            "rowHeight": 30
        }
    )

    # =====================================================
    # 헤더 고정
    # =====================================================

    worksheet.freeze(
        rows=2
    )

    print(
        f"Google Sheets 전력분석 업데이트 완료: "
        f"{len(teams)}개 팀"
    )

    return spreadsheet.url
