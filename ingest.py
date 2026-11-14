import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

CSV_PATH = Path("data/Car_Data.csv")
SCHEMA = "raw_data"
TABLE = CSV_PATH.stem.lower()  # ตั้งชื่อตารางตามชื่อไฟล์ -> car_data


def get_engine():
    url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
        f"/{os.getenv('POSTGRES_DB')}"
    )
    return create_engine(url)


def ingest():
    print(f"Reading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df):,} rows, {len(df.columns)} columns")

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    # raw data: เก็บตามต้นฉบับ ไม่แก้ไขอะไร
    df.to_sql(
        name=TABLE,
        con=engine,
        schema=SCHEMA,
        if_exists="replace",   # รันซ้ำได้ ไม่ข้อมูลซ้ำ
        index=False,
        chunksize=10_000,
        method="multi",
    )

    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.{TABLE}")).scalar()
    print(f"Done: {SCHEMA}.{TABLE} has {count:,} rows")


if __name__ == "__main__":
    ingest()