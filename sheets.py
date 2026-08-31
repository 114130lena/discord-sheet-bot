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
WORKSHEET_TITLE = "전력분석"
BLOCK_ROWS = 24
BLOCK_GAP = 1
MAX_ROWS = 1000


def _safe_title(title):
    title = re.sub(r"[\\/*?:\[\]]", "_", str(title or WORKSHEET_TITLE))
    return title[:100] or WORKSHEET_TITLE


def get_or_create_worksheet(spreadsheet):
    try:
        return spreadsheet.worksheet(WORKSHEET_TITLE)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=WORKSHEET_TITLE, rows=MAX_ROWS, cols=10)


def _find_session_row(ws, session_id):
    marker = f"SESSION_ID:{session_id}"
    try:
        values = ws.get_all_values()
    except Exception:
        return None
    for idx, row in enumerate(values):
        if marker in row:
            return idx
    return None


def _find_new_row(ws):
    try:
        values = ws.get_all_values()
    except Exception:
        return 0
    last = -1
    for i, row in enumerate(values):
        if any(str(v).strip() for v in row):
            last = i
    return last + 1 + BLOCK_GAP


def _ensure_rows(ws, required_end):
    if required_end <= ws.row_count:
        return
    ws.add_rows(required_end - ws.row_count + 20)


def _style(bg, bold=False, size=10, fg=None, align="CENTER"):
    fmt = {
        "backgroundColor": bg,
        "textFormat": {"bold": bold, "fontSize": size},
        "horizontalAlignment": align,
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "WRAP",
    }
    if fg:
        fmt["textFormat"]["foregroundColor"] = fg
    return fmt


def update_spreadsheet(project):
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    ws = get_or_create_worksheet(spreadsheet)
    sid = ws.id

    teams = list(project.get("teams", []))[:8]
    session_id = str(project.get("session_id") or project.get("id") or "-")
    session_name = str(project.get("session_name") or f"세션 {session_id}")
    event_name = str(project.get("event_name") or "")
    status = {"active": "진행 중", "paused": "보류", "completed": "완료"}.get(project.get("session_status"), "진행 중")
    created = str(project.get("session_created_at") or "-").replace("T", " ")
    updated = str(project.get("session_updated_at") or "-").replace("T", " ")
    batches = project.get("session_batches", [])

    stored_row = project.get("sheet_row_start")
    row = None
    if isinstance(stored_row, int) and stored_row >= 0 and stored_row < ws.row_count:
        try:
            marker = ws.cell(stored_row + 1, 1).value
            if marker == f"SESSION_ID:{session_id}":
                row = stored_row
        except Exception:
            row = None
    if row is None:
        row = _find_session_row(ws, session_id)
    if row is None:
        row = _find_new_row(ws)

    end_row = row + BLOCK_ROWS
    _ensure_rows(ws, end_row + 2)
    project["sheet_row_start"] = row
    project["sheet_title"] = WORKSHEET_TITLE

    clear_range = {
        "sheetId": sid,
        "startRowIndex": row,
        "endRowIndex": end_row,
        "startColumnIndex": 0,
        "endColumnIndex": 9,
    }
    requests = [
        {"unmergeCells": {"range": clear_range}},
        {"updateCells": {"range": clear_range, "fields": "userEnteredValue,userEnteredFormat"}},
        {"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row + 1, "startColumnIndex": 0, "endColumnIndex": 9}, "mergeType": "MERGE_ALL"}},
    ]

    title = f"📊 전력분석 · {session_name}"
    requests.append({"updateCells": {
        "rows": [{"values": [{"userEnteredValue": {"stringValue": title}, "userEnteredFormat": _style({"red": 0.09, "green": 0.13, "blue": 0.18}, True, 18, {"red": 1, "green": 1, "blue": 1})}]}],
        "start": {"sheetId": sid, "rowIndex": row, "columnIndex": 0},
        "fields": "userEnteredValue,userEnteredFormat"
    }})

    meta = f"SESSION_ID:{session_id} | 대회: {event_name or '-'} | 상태: {status} | 생성: {created} | 최근 수정: {updated} | 분석 묶음: {len(batches)}회 | 누적: {len(teams)}/8팀"
    requests.append({"updateCells": {
        "rows": [{"values": [{"userEnteredValue": {"stringValue": meta}, "userEnteredFormat": _style({"red": 0.94, "green": 0.96, "blue": 0.98}, True, 9)}]}],
        "start": {"sheetId": sid, "rowIndex": row + 1, "columnIndex": 0},
        "fields": "userEnteredValue,userEnteredFormat"
    }})
    requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row + 1, "endRowIndex": row + 2, "startColumnIndex": 0, "endColumnIndex": 9}, "mergeType": "MERGE_ALL"}})

    headers = ["팀", "선수", "실험체", "분석 메모"]
    header_bg = {"red": 0.20, "green": 0.29, "blue": 0.38}
    for start_col in (0, 5):
        requests.append({"updateCells": {
            "rows": [{"values": [{"userEnteredValue": {"stringValue": h}, "userEnteredFormat": _style(header_bg, True, 11, {"red": 1, "green": 1, "blue": 1})} for h in headers]}],
            "start": {"sheetId": sid, "rowIndex": row + 2, "columnIndex": start_col},
            "fields": "userEnteredValue,userEnteredFormat"
        }})

    team_colors = [
        ({"red": 0.14, "green": 0.32, "blue": 0.52}, {"red": 0.91, "green": 0.95, "blue": 0.98}),
        ({"red": 0.34, "green": 0.22, "blue": 0.50}, {"red": 0.95, "green": 0.92, "blue": 0.98}),
        ({"red": 0.10, "green": 0.39, "blue": 0.32}, {"red": 0.90, "green": 0.96, "blue": 0.94}),
        ({"red": 0.52, "green": 0.29, "blue": 0.12}, {"red": 0.98, "green": 0.94, "blue": 0.89}),
    ]
    border = {"style": "SOLID", "color": {"red": 0.55, "green": 0.60, "blue": 0.65}}
    thick = {"style": "SOLID_MEDIUM", "color": {"red": 0.35, "green": 0.40, "blue": 0.45}}

    def add_team(team, team_row, col, idx):
        try:
            size = 3 if int(team.get("roster_size", 4)) == 3 else 4
        except Exception:
            size = 4
        name = str(team.get("team_name", "")).strip()
        tag = str(team.get("team_tag", "")).strip()
        display = f"{name}\n[{tag}]" if name and tag else (name or (f"[{tag}]" if tag else ""))
        players = [str(team.get(f"player{i}", "")) for i in range(1, 5)][:size]
        experiments = [str(team.get(f"experiment{i}", "")) for i in range(1, 5)][:size]
        memo = str(team.get("notes", "") or team.get("strategy", "") or "")
        dark, light = team_colors[idx % len(team_colors)]

        for c in (col, col + 3):
            requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": team_row, "endRowIndex": team_row + size, "startColumnIndex": c, "endColumnIndex": c + 1}, "mergeType": "MERGE_ALL"}})
        requests.append({"updateCells": {"rows": [{"values": [{"userEnteredValue": {"stringValue": display}, "userEnteredFormat": _style(dark, True, 15, {"red": 1, "green": 1, "blue": 1})}]}], "start": {"sheetId": sid, "rowIndex": team_row, "columnIndex": col}, "fields": "userEnteredValue,userEnteredFormat"}})
        requests.append({"updateCells": {"rows": [{"values": [{"userEnteredValue": {"stringValue": memo}, "userEnteredFormat": _style({"red": 0.97, "green": 0.97, "blue": 0.97}, False, 10, None, "LEFT")}]}], "start": {"sheetId": sid, "rowIndex": team_row, "columnIndex": col + 3}, "fields": "userEnteredValue,userEnteredFormat"}})

        rows = []
        for i, player in enumerate(players):
            rows.append({"values": [
                {"userEnteredValue": {"stringValue": player}, "userEnteredFormat": _style(light, False, 10)},
                {"userEnteredValue": {"stringValue": experiments[i] if i < len(experiments) else ""}, "userEnteredFormat": _style(light, False, 10)},
            ]})
        requests.append({"updateCells": {"rows": rows, "start": {"sheetId": sid, "rowIndex": team_row, "columnIndex": col + 1}, "fields": "userEnteredValue,userEnteredFormat"}})
        requests.append({"updateBorders": {"range": {"sheetId": sid, "startRowIndex": team_row, "endRowIndex": team_row + size, "startColumnIndex": col, "endColumnIndex": col + 4}, "top": thick, "bottom": thick, "left": thick, "right": thick, "innerHorizontal": border, "innerVertical": border}})
        requests.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": team_row, "endIndex": team_row + size}, "properties": {"pixelSize": 38}, "fields": "pixelSize"}})

    left = teams[0::2]
    right = teams[1::2]
    data_start = row + 3
    for i, team in enumerate(left):
        add_team(team, data_start + i * 5, 0, i * 2)
    for i, team in enumerate(right):
        add_team(team, data_start + i * 5, 5, i * 2 + 1)

    widths = {0: 180, 1: 125, 2: 110, 3: 280, 4: 25, 5: 180, 6: 125, 7: 110, 8: 280}
    for c, width in widths.items():
        requests.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1}, "properties": {"pixelSize": width}, "fields": "pixelSize"}})
    requests.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True, "frozenRowCount": 0}}, "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount"}})

    spreadsheet.batch_update({"requests": requests})
    url = f"{spreadsheet.url}#gid={sid}"
    print(f"Google Sheets 업데이트 완료: 세션 {session_id} / {len(teams)}개 팀 / {len(batches)}회 분석 / row={row + 1}")
    return url
