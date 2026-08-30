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

SPREADSHEET_ID = "1FARr4g1gNM1P9oaFvpFSd3xWJo1BtgBy9398WwlzU8M"


# =========================================================
# Worksheet
# =========================================================

def get_or_create_worksheet(spreadsheet):

    try:
        return spreadsheet.worksheet("전력분석")

    except gspread.WorksheetNotFound:

        return spreadsheet.add_worksheet(
            title="전력분석",
            rows=200,
            cols=12
        )


# =========================================================
# Google Sheets 업데이트
# =========================================================

def update_spreadsheet(project):

    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    worksheet = get_or_create_worksheet(
        spreadsheet
    )

    sheet_id = worksheet.id

    teams = project.get("teams", [])

    # =====================================================
    # 1. 기존 내용 초기화
    # =====================================================

    requests = [

        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 200,
                    "startColumnIndex": 0,
                    "endColumnIndex": 12
                },
                "fields": "userEnteredValue,userEnteredFormat"
            }
        },

        # 기존 병합 제거
        {
            "unmergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 200,
                    "startColumnIndex": 0,
                    "endColumnIndex": 12
                }
            }
        }
    ]

    # =====================================================
    # 2. 제목
    # =====================================================

    requests.append({
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": 9
            },
            "mergeType": "MERGE_ALL"
        }
    })

    requests.append({
        "updateCells": {
            "rows": [
                {
                    "values": [
                        {
                            "userEnteredValue": {
                                "stringValue": "2026 전력분석"
                            },
                            "userEnteredFormat": {
                                "textFormat": {
                                    "bold": True,
                                    "fontSize": 16
                                },
                                "horizontalAlignment": "LEFT",
                                "verticalAlignment": "MIDDLE"
                            }
                        }
                    ]
                }
            ],
            "start": {
                "sheetId": sheet_id,
                "rowIndex": 0,
                "columnIndex": 0
            },
            "fields": "userEnteredValue,userEnteredFormat"
        }
    })

    # =====================================================
    # 3. 헤더
    # =====================================================

    headers = [
        "팀",
        "선수",
        "실험체",
        "운영 전략 / 교전 포인트"
    ]

    # 왼쪽 헤더
    requests.append({
        "updateCells": {
            "rows": [
                {
                    "values": [
                        {
                            "userEnteredValue": {
                                "stringValue": value
                            },
                            "userEnteredFormat": {
                                "textFormat": {
                                    "bold": True,
                                    "fontSize": 11
                                },
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "wrapStrategy": "WRAP"
                            }
                        }
                        for value in headers
                    ]
                }
            ],
            "start": {
                "sheetId": sheet_id,
                "rowIndex": 1,
                "columnIndex": 0
            },
            "fields": "userEnteredValue,userEnteredFormat"
        }
    })

    # 오른쪽 헤더
    requests.append({
        "updateCells": {
            "rows": [
                {
                    "values": [
                        {
                            "userEnteredValue": {
                                "stringValue": value
                            },
                            "userEnteredFormat": {
                                "textFormat": {
                                    "bold": True,
                                    "fontSize": 11
                                },
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "wrapStrategy": "WRAP"
                            }
                        }
                        for value in headers
                    ]
                }
            ],
            "start": {
                "sheetId": sheet_id,
                "rowIndex": 1,
                "columnIndex": 5
            },
            "fields": "userEnteredValue,userEnteredFormat"
        }
    })

    # =====================================================
    # 4. 팀 데이터 생성
    # =====================================================

    left_teams = teams[0::2]
    right_teams = teams[1::2]

    # -----------------------------------------------------
    # 팀 하나를 requests에 추가
    # -----------------------------------------------------

    def add_team(
        team,
        start_row,
        start_col
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
        # 팀명 + 약칭
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
        # 팀명 셀 병합
        # ---------------------------------------------

        requests.append({
            "mergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row,
                    "endRowIndex": start_row + 4,
                    "startColumnIndex": start_col,
                    "endColumnIndex": start_col + 1
                },
                "mergeType": "MERGE_ALL"
            }
        })

        # ---------------------------------------------
        # 팀명
        # ---------------------------------------------

        requests.append({
            "updateCells": {
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "stringValue": display_name
                                },
                                "userEnteredFormat": {
                                    "textFormat": {
                                        "bold": True,
                                        "fontSize": 11
                                    },
                                    "horizontalAlignment": "CENTER",
                                    "verticalAlignment": "MIDDLE",
                                    "wrapStrategy": "WRAP"
                                }
                            }
                        ]
                    }
                ],
                "start": {
                    "sheetId": sheet_id,
                    "rowIndex": start_row,
                    "columnIndex": start_col
                },
                "fields": "userEnteredValue,userEnteredFormat"
            }
        })

        # ---------------------------------------------
        # 선수 4명
        # ---------------------------------------------

        rows = []

        for player in players:

            rows.append({
                "values": [

                    {
                        "userEnteredValue": {
                            "stringValue": player
                        },
                        "userEnteredFormat": {
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },

                    {
                        "userEnteredValue": {
                            "stringValue": ""
                        }
                    },

                    {
                        "userEnteredValue": {
                            "stringValue": ""
                        },
                        "userEnteredFormat": {
                            "wrapStrategy": "WRAP",
                            "verticalAlignment": "MIDDLE"
                        }
                    }
                ]
            })

        requests.append({
            "updateCells": {
                "rows": rows,
                "start": {
                    "sheetId": sheet_id,
                    "rowIndex": start_row,
                    "columnIndex": start_col + 1
                },
                "fields": "userEnteredValue,userEnteredFormat"
            }
        })

        # ---------------------------------------------
        # 행 높이
        # ---------------------------------------------

        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start_row,
                    "endIndex": start_row + 4
                },
                "properties": {
                    "pixelSize": 35
                },
                "fields": "pixelSize"
            }
        })

    # =====================================================
    # 5. 왼쪽 팀
    # =====================================================

    row = 2

    for team in left_teams:

        add_team(
            team,
            row,
            0
        )

        row += 4

    # =====================================================
    # 6. 오른쪽 팀
    # =====================================================

    row = 2

    for team in right_teams:

        add_team(
            team,
            row,
            5
        )

        row += 4

    # =====================================================
    # 7. 열 너비
    # =====================================================

    column_widths = {
        0: 170,   # A 팀
        1: 120,   # B 선수
        2: 110,   # C 실험체
        3: 320,   # D 전략
        4: 25,    # E 여백
        5: 170,   # F 팀
        6: 120,   # G 선수
        7: 110,   # H 실험체
        8: 320    # I 전략
    }

    for column, width in column_widths.items():

        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": column,
                    "endIndex": column + 1
                },
                "properties": {
                    "pixelSize": width
                },
                "fields": "pixelSize"
            }
        })

    # =====================================================
    # 8. 헤더 고정
    # =====================================================

    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {
                    "frozenRowCount": 2
                }
            },
            "fields": "gridProperties.frozenRowCount"
        }
    })

    # =====================================================
    # 9. 한 번에 Google Sheets로 전송
    # =====================================================

    spreadsheet.batch_update({
        "requests": requests
    })

    print(
        f"Google Sheets 업데이트 완료: "
        f"{len(teams)}개 팀"
    )

    return spreadsheet.url
