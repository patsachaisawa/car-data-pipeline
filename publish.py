import os

import gspread
import pandas as pd
from dotenv import load_dotenv
from gspread_dataframe import set_with_dataframe

from ingest import get_engine

load_dotenv()

SCHEMA = "production"
# ส่งเฉพาะตารางสรุป ไม่ส่ง car_clean (100,000 แถว) เพราะเกินความจำเป็นและช้า
TABLES = [
    "agg_brand",
    "agg_year",
    "agg_mileage_bucket",
    "agg_condition_brand",
    "agg_color",
    "agg_model",
    "agg_price_segment",
]
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Google Sheets จำกัด 10 ล้าน cell ต่อไฟล์ ตั้งเพดานปลอดภัยไว้ต่ำกว่านั้นมาก
MAX_CELLS_PER_TABLE = 2_000_000


def get_worksheet(spreadsheet, title: str, rows: int, cols: int):
    """ใช้ tab เดิมถ้ามี (ล้างข้อมูลเก่า) ไม่มีก็สร้างใหม่ -> รันซ้ำได้"""
    try:
        ws = spreadsheet.worksheet(title)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
    return ws


def publish():
    if not SHEET_ID:
        raise SystemExit("GOOGLE_SHEET_ID is not set in .env")

    engine = get_engine()
    client = gspread.service_account(filename=CREDENTIALS_FILE)
    spreadsheet = client.open_by_key(SHEET_ID)

    total_cells = 0
    for table in TABLES:
        df = pd.read_sql(f"SELECT * FROM {SCHEMA}.{table}", engine)
        cells = df.shape[0] * df.shape[1]
        if cells > MAX_CELLS_PER_TABLE:
            raise SystemExit(f"{table} has {cells:,} cells, too large for Sheets. Aggregate it first.")

        ws = get_worksheet(spreadsheet, table, rows=len(df) + 1, cols=len(df.columns))
        set_with_dataframe(ws, df, include_index=False, resize=True)
        total_cells += cells
        print(f"Published {table}: {len(df):,} rows x {len(df.columns)} cols")

    print(f"Done: {len(TABLES)} tabs, {total_cells:,} cells total")


if __name__ == "__main__":
    publish()