"""Entry point. Run: uvicorn backend.main:app --reload --port 8000"""
from backend.api.routes import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
