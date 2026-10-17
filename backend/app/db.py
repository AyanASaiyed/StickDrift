import os
from pathlib import Path

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("TIMESCALE_SERVICE_URL")
if not DATABASE_URL:
    raise RuntimeError("Set DATABASE_URL or TIMESCALE_SERVICE_URL in backend/.env.")

pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=5,
    kwargs={"row_factory": dict_row},
    open=False,
)
