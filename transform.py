import pandas as pd
from sqlalchemy import text

from ingest import get_engine

SRC_SCHEMA = "raw_data"
SRC_TABLE = "car_data"
DST_SCHEMA = "production"
REFERENCE_YEAR = 2026  # ใช้คำนวณอายุรถ

PRICE_BINS = [0, 20_000, 40_000, 60_000, float("inf")]
PRICE_LABELS = ["Budget (<=20k)", "Mid (20-40k)", "High (40-60k)", "Premium (>60k)"]
MILEAGE_BINS = [-1, 50_000, 100_000, 150_000, float("inf")]
MILEAGE_LABELS = ["0-50k", "50-100k", "100-150k", "150k+"]


# ---------- 1. Extract ----------
def read_raw(engine) -> pd.DataFrame:
    query = f"SELECT * FROM {SRC_SCHEMA}.{SRC_TABLE}"
    df = pd.read_sql(query, engine)
    print(f"Read {len(df):,} rows from {SRC_SCHEMA}.{SRC_TABLE}")
    return df


# ---------- 2. Cleaning ----------
def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    before = len(df)

    # ตัดช่องว่างและทำรูปแบบข้อความให้เป็นมาตรฐาน
    for col in ["brand", "model", "color", "condition"]:
        df[col] = df[col].astype("string").str.strip()
    df["condition"] = df["condition"].str.title()
    df["color"] = df["color"].str.title()

    # บังคับชนิดข้อมูลตัวเลข (ค่าที่แปลงไม่ได้จะกลายเป็น NaN)
    for col in ["id", "year", "mileage", "price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Missing values / duplicates
    df = df.dropna(subset=["id", "brand", "model", "year", "mileage", "price", "condition"])
    df = df.drop_duplicates(subset="id")

    # ตัดค่าที่เป็นไปไม่ได้
    df = df[
        (df["price"] > 0)
        & (df["mileage"] >= 0)
        & (df["year"].between(1900, REFERENCE_YEAR))
    ]

    df = df.astype({"id": "int64", "year": "int64", "mileage": "int64", "price": "int64"})
    print(f"Cleaning: {before:,} -> {len(df):,} rows (removed {before - len(df):,})")
    return df.reset_index(drop=True)


# ---------- 3. Feature engineering ----------
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["age"] = REFERENCE_YEAR - df["year"]
    df["decade"] = (df["year"] // 10 * 10).astype(str) + "s"
    df["mileage_bucket"] = pd.cut(
        df["mileage"], bins=MILEAGE_BINS, labels=MILEAGE_LABELS
    ).astype("string")
    df["price_segment"] = pd.cut(
        df["price"], bins=PRICE_BINS, labels=PRICE_LABELS
    ).astype("string")
    df["is_generic_model"] = df["model"].str.startswith("Generic")
    df["price_per_1k_mileage"] = (df["price"] / (df["mileage"].clip(lower=1) / 1000)).round(2)
    df["is_new"] = (df["condition"] == "New").astype(int)
    return df


# ---------- 4. Aggregation (หนึ่งตารางต่อหนึ่งคำถาม) ----------
def build_aggregates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}

    # Q1: ยี่ห้อ - จำนวนและราคาเฉลี่ย
    out["agg_brand"] = (
        df.groupby("brand")
        .agg(car_count=("id", "count"), avg_price=("price", "mean"),
             min_price=("price", "min"), max_price=("price", "max"),
             avg_mileage=("mileage", "mean"), pct_new=("is_new", "mean"))
        .assign(pct_new=lambda x: x["pct_new"] * 100)
        .round(2).reset_index().sort_values("car_count", ascending=False)
    )

    # Q2: ปีที่ผลิต
    out["agg_year"] = (
        df.groupby("year")
        .agg(car_count=("id", "count"), avg_price=("price", "mean"),
             avg_mileage=("mileage", "mean"))
        .round(2).reset_index()
    )

    # Q3: ช่วงไมล์
    mb = (
        df.groupby("mileage_bucket")
        .agg(car_count=("id", "count"), avg_price=("price", "mean"))
        .round(2).reset_index()
    )
    mb["sort_order"] = mb["mileage_bucket"].map({l: i for i, l in enumerate(MILEAGE_LABELS)})
    out["agg_mileage_bucket"] = mb.sort_values("sort_order")

    # Q4: New vs Used แยกยี่ห้อ
    out["agg_condition_brand"] = (
        df.groupby(["brand", "condition"])
        .agg(car_count=("id", "count"), avg_price=("price", "mean"))
        .round(2).reset_index()
    )

    # Q5: สี
    out["agg_color"] = (
        df.groupby("color")
        .agg(car_count=("id", "count"), avg_price=("price", "mean"))
        .assign(share_pct=lambda x: x["car_count"] / x["car_count"].sum() * 100)
        .round(2).reset_index().sort_values("car_count", ascending=False)
    )

    # Q6: รุ่นที่มีชื่อจริง (ไม่รวม Generic)
    out["agg_model"] = (
        df[~df["is_generic_model"]]
        .groupby(["brand", "model"])
        .agg(car_count=("id", "count"), avg_price=("price", "mean"))
        .round(2).reset_index().sort_values("avg_price", ascending=False)
    )

    # Q7: องค์ประกอบของแต่ละกลุ่มราคา (รูปแบบ long: segment / dimension / category)
    parts = []
    for dim in ["brand", "condition", "decade"]:
        t = (df.groupby(["price_segment", dim]).size()
               .rename("car_count").reset_index()
               .rename(columns={dim: "category"}))
        t["dimension"] = dim
        parts.append(t)
    seg = pd.concat(parts, ignore_index=True)
    seg["share_pct"] = (
        seg["car_count"] / seg.groupby(["price_segment", "dimension"])["car_count"].transform("sum") * 100
    ).round(2)
    out["agg_price_segment"] = seg[["price_segment", "dimension", "category", "car_count", "share_pct"]]

    return out


# ---------- 5. Load ----------
def write_tables(engine, tables: dict[str, pd.DataFrame]) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DST_SCHEMA}"))
    for name, frame in tables.items():
        frame.to_sql(name, engine, schema=DST_SCHEMA, if_exists="replace",
                     index=False, chunksize=10_000, method="multi")
        print(f"Wrote {DST_SCHEMA}.{name}: {len(frame):,} rows")


def transform():
    engine = get_engine()
    clean_df = add_features(clean(read_raw(engine)))
    tables = {"car_clean": clean_df, **build_aggregates(clean_df)}
    write_tables(engine, tables)
    print("Transform complete")


if __name__ == "__main__":
    transform()
