"""Mock photo provider for placeholder avatars."""

from __future__ import annotations

from providers.base import PhotoProvider


class MockPhotoProvider(PhotoProvider):
    """Return deterministic placeholder URL for local use."""

    def get_photo_url(self, *, employee_id: str) -> str:
        return f"https://api.dicebear.com/9.x/initials/svg?seed={employee_id}"
