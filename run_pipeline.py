import sys
import time

from ingest import ingest, get_engine
from transform import transform
from publish import publish


def wait_for_db(retries: int = 10, delay: int = 3) -> None:
    """รอให้ PostgreSQL พร้อมก่อนเริ่ม (กรณีเพิ่งสั่ง docker compose up)"""
    engine = get_engine()
    for attempt in range(1, retries + 1):
        try:
            with engine.connect():
                return
        except Exception as exc:
            print(f"Waiting for database ({attempt}/{retries}): {exc.__class__.__name__}")
            time.sleep(delay)
    raise SystemExit("Database is not reachable. Run `docker compose up -d` first.")


def run_step(name: str, func) -> None:
    print(f"\n=== {name} ===")
    start = time.time()
    func()
    print(f"--- {name} finished in {time.time() - start:.1f}s ---")


def main() -> None:
    start = time.time()
    wait_for_db()
    try:
        run_step("1/3 Ingest   (CSV -> raw_data)", ingest)
        run_step("2/3 Transform (raw_data -> production)", transform)
        run_step("3/3 Publish  (production -> Google Sheets)", publish)
    except Exception as exc:
        print(f"\nPipeline FAILED: {exc.__class__.__name__}: {exc}")
        sys.exit(1)
    print(f"\nPipeline completed in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()