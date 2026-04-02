from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import collect, convert, measures

app = FastAPI(title="Measures API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(measures.router)
app.include_router(collect.router)
app.include_router(convert.router)


@app.get("/api/health")
def health() -> dict:
    measures_dir = settings.measures_dir_resolved
    file_count = len(list(measures_dir.glob("*.yaml"))
                     ) if measures_dir.exists() else 0
    return {
        "status": "ok",
        "measures_dir": str(measures_dir),
        "yaml_files": file_count,
    }
