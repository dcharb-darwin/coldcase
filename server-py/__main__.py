"""
Entry point for running the backend directly: `python server-py/__main__.py`.
Prefer `./dev.sh` or `npm run api` for dev, which source .env first.
"""

import uvicorn

from core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    main()
