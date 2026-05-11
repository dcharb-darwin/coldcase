"""
MongoDB connection management via MongoEngine.
"""

import mongoengine
from core.config import get_settings

_connected = False


def init_database() -> None:
    """Connect to MongoDB. Safe to call multiple times."""
    global _connected
    if _connected:
        return

    settings = get_settings()
    mongoengine.connect(
        db=settings.database_name,
        host=settings.mongodb_uri,
        alias="default",
    )
    _connected = True
    print(f"✅ Connected to MongoDB: {settings.database_name}")


def close_database() -> None:
    """Disconnect from MongoDB."""
    global _connected
    if _connected:
        mongoengine.disconnect(alias="default")
        _connected = False
        print("🔌 Disconnected from MongoDB")
