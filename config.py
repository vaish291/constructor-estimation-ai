import os


class Config:
    """
    Central application configuration.

    MySQL is the primary supported database. Set the MYSQL_HOST environment
    variable (plus MYSQL_USER / MYSQL_PASSWORD / MYSQL_DB / MYSQL_PORT as
    needed) to connect to a real MySQL server, e.g.:

        export MYSQL_HOST=localhost
        export MYSQL_USER=root
        export MYSQL_PASSWORD=secret
        export MYSQL_DB=construction_estimator

    If MYSQL_HOST is not set, the app automatically falls back to a local
    SQLite database (construction.db) so it can still run out-of-the-box
    for local development/testing without a MySQL server installed.
    """

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "").strip()
    MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DB = os.environ.get("MYSQL_DB", "construction_estimator")

    SECRET_KEY = os.environ.get("SECRET_KEY", "buildai-construction-estimator-secret")

    # Business defaults (used unless overridden per-request from the UI)
    DEFAULT_GST_PCT = float(os.environ.get("DEFAULT_GST_PCT", 18.0))
    DEFAULT_WASTAGE_PCT = float(os.environ.get("DEFAULT_WASTAGE_PCT", 5.0))
    DEFAULT_PROFIT_PCT = float(os.environ.get("DEFAULT_PROFIT_PCT", 15.0))

    @staticmethod
    def get_database_uri():
        if Config.MYSQL_HOST:
            return (
                f"mysql+pymysql://{Config.MYSQL_USER}:{Config.MYSQL_PASSWORD}"
                f"@{Config.MYSQL_HOST}:{Config.MYSQL_PORT}/{Config.MYSQL_DB}"
                f"?charset=utf8mb4"
            )
        return "sqlite:///construction.db"

    @staticmethod
    def using_mysql():
        return bool(Config.MYSQL_HOST)
