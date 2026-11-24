"""
Project package.

When DB_ENGINE=mysql we use PyMySQL (pure Python, installs on Windows without
a C compiler) as a drop-in replacement for the mysqlclient driver.
"""
import os

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

if os.getenv("DB_ENGINE", "sqlite").strip().lower() == "mysql":
    try:
        import pymysql

        # Django checks the mysqlclient version; PyMySQL is API-compatible.
        pymysql.version_info = (2, 2, 1, "final", 0)
        pymysql.install_as_MySQLdb()
    except ImportError:  # pragma: no cover - only hit when PyMySQL is missing
        pass
