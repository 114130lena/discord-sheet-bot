import re
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = Credentials.from_service_account_file("google-service-account.json", scopes=SCOPES)
gc = gspread.authorize(credentials)
SPREADSHEET_ID = "1FARr4g1gNM1P9oaFvpFSd3xWJo1BtgBy9398WwlzU8M"


def _safe_title(title):
    title = re.sub(r"[\\/*?:\[\]]", "_", str(title or "전력분석"))
    return title[:100] or "전력분석"


def get_or_create_worksheet(spreadsheet, title):
    title = _safe_title(title)
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=400, cols=10)


def update_spreadsheet(project):
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    title = _safe_title(project.get("sheet_title") or f"전력분석_{project.get('session_id', project.get('id', 'session'))}")
    ws = get_or_create_worksheet(spreadsheet, title)
    sid = ws.id
    teams = project.get("teams", [])
    batches = project.get("session_batches", [])
    session_id = str(project.get("session_id") or project.get("id") or "-")
    requests = []

    base = {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 400, "startColumnIndex": 0, "endColumnIndex": 10}
    requests.append({"unmergeCells": {"range": base}})
    requests.append({"updateCells": {"range": base, "fields": "userEnteredValue,userEnteredFormat"}})

    requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 9}, "mergeType": "MERGE_ALL"}})
    requests.append({"updateCells": {
        "rows": [{"values": [{"userEnteredValue": {"stringValue": "📊 전력분석 세션"}, "userEnteredFormat": {
            "backgroundColor": {"red": 0.09, "green": 0.13, "blue": 0.18},
            "textFormat": {"bold": True, "fontSize": 18, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"
        }}]}], "start": {"sheetId": sid, "rowIndex": 0, "columnIndex": 0}, "fields": "userEnteredValue,userEnteredFormat"
    }})

    session_info = f"세션 ID: {session_id}  |  분석 묶음: {len(batches)}회  |  누적 팀: {len(teams)}팀"
    requests.append({"updateCells": {
        "rows": [{"values": [{"userEnteredValue": {"stringValue": session_info}, "userEnteredFormat": {
            "backgroundColor": {"red": 0.94, "green": 0.96, "blue": 0.98},
            "textFormat": {"bold": True, "fontSize": 10},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"
        }}]}], "start": {"sheetId": sid, "rowIndex": 1, "columnIndex": 0}, "fields": "userEnteredValue,userEnteredFormat"
    }})
    requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 9}, "mergeType": "MERGE_ALL"}})

    headers = ["팀", "선수", "실험체", "분석 메모"]
    for start_col in (0, 5):
        requests.append({"updateCells": {
            "rows": [{"values": [{"userEnteredValue": {"stringValue": h}, "userEnteredFormat": {
                "backgroundColor": {"red": 0.20, "green": 0.29, "blue": 0.38},
                "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"
            }} for h in headers]}], "start": {"sheetId": sid, "rowIndex": 2, "columnIndex": start_col}, "fields": "userEnteredValue,userEnteredFormat"
        }})

    team_colors = [
        ({"red": 0.14, "green": 0.32, "blue": 0.52}, {"red": 0.91, "green": 0.95, "blue": 0.98}),
        ({"red": 0.34, "green": 0.22, "blue": 0.50}, {"red": 0.95, "green": 0.92, "blue": 0.98}),
        ({"red": 0.10, "green": 0.39, "blue": 0.32}, {"red": 0.90, "green": 0.96, "blue": 0.94}),
        ({"red": 0.52, "green": 0.29, "blue": 0.12}, {"red": 0.98, "green": 0.94, "blue": 0.89}),
    ]
    border = {"style": "SOLID", "color": {"red": 0.55, "green": 0.60, "blue": 0.65}}
    thick = {"style": "SOLID_MEDIUM", "color": {"red": 0.35, "green": 0.40, "blue": 0.45}}

    def add_team(team, row, col, idx):
        try:
            size = 3 if int(team.get("roster_size", 4)) == 3 else 4
        except Exception:
            size = 4
        name = str(team.get("team_name", "")).strip()
        tag = str(team.get("team_tag", "")).strip()
        display = f"{name}\n[{tag}]" if name and tag else (name or (f"[{tag}]" if tag else ""))
        players = [str(team.get(f"player{i}", "")) for i in range(1, 5)][:size]
        memo = str(team.get("notes", "") or team.get("strategy", "") or "")
        dark, light = team_colors[idx % len(team_colors)]

        for c in (col, col + 3):
            requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row + size, "startColumnIndex": c, "endColumnIndex": c + 1}, "mergeType": "MERGE_ALL"}})

        requests.append({"updateCells": {
            "rows": [{"values": [{"userEnteredValue": {"stringValue": display}, "userEnteredFormat": {
                "backgroundColor": dark, "textFormat": {"bold": True, "fontSize": 15, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"
            }}]}], "start": {"sheetId": sid, "rowIndex": row, "columnIndex": col}, "fields": "userEnteredValue,userEnteredFormat"
        }})
        requests.append({"updateCells": {
            "rows": [{"values": [{"userEnteredValue": {"stringValue": memo}, "userEnteredFormat": {
                "backgroundColor": {"red": 0.97, "green": 0.97, "blue": 0.97}, "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"
            }}]}], "start": {"sheetId": sid, "rowIndex": row, "columnIndex": col + 3}, "fields": "userEnteredValue,userEnteredFormat"
        }})

        rows = []
        for player in players:
            rows.append({"values": [
                {"userEnteredValue": {"stringValue": player}, "userEnteredFormat": {"backgroundColor": light, "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}},
                {"userEnteredValue": {"stringValue": ""}, "userEnteredFormat": {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}},
            ]})
        requests.append({"updateCells": {"rows": rows, "start": {"sheetId": sid, "rowIndex": row, "columnIndex": col + 1}, "fields": "userEnteredValue,userEnteredFormat"}})

        requests.append({"updateBorders": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row + size, "startColumnIndex": col, "endColumnIndex": col + 4}, "top": thick, "bottom": thick, "left": thick, "right": thick, "innerHorizontal": border, "innerVertical": border}})
        requests.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": row, "endIndex": row + size}, "properties": {"pixelSize": 38}, "fields": "pixelSize"}})

    left = teams[0::2]
    right = teams[1::2]
    row = 3
    for i, team in enumerate(left):
        add_team(team, row, 0, i * 2)
        row += max(4, int(team.get("roster_size", 4))) + 1
    row = 3
    for i, team in enumerate(right):
        add_team(team, row, 5, i * 2 + 1)
        row += max(4, int(team.get("roster_size", 4))) + 1

    widths = {0: 180, 1: 125, 2: 110, 3: 280, 4: 25, 5: 180, 6: 125, 7: 110, 8: 280}
    for c, width in widths.items():
        requests.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1}, "properties": {"pixelSize": width}, "fields": "pixelSize"}})
    requests.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 3}}, "fields": "gridProperties.frozenRowCount"}})
    requests.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}}, "fields": "gridProperties.hideGridlines"}})

    spreadsheet.batch_update({"requests": requests})
    url = f"{spreadsheet.url}#gid={sid}"
    print(f"Google Sheets 업데이트 완료: 세션 {session_id} / {len(teams)}개 팀 / {len(batches)}회 분석")
    return url
