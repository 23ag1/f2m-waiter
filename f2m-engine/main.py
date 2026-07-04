import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from f2m_engine.api import create_app

def _build_dsn() -> str:
    if dsn := os.environ.get("POSTGRES_DSN"):
        return dsn
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "f2m_platform")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

POSTGRES_DSN = _build_dsn()
ENGINE_DATA_DIR = os.environ.get("ENGINE_DATA_DIR", "/app/engine_data")

app = create_app(dsn=POSTGRES_DSN, derived_dir=ENGINE_DATA_DIR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=1488, reload=False)
