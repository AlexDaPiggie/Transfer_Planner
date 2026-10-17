"""Serve website assets without exposing local launch scripts or server logs."""
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        parts = path.replace("\\", "/").split("/")
        if path not in (".", "", "index.html"):
            if parts[0] not in ("js", "css", "vendor") or any(part.startswith(".") for part in parts):
                raise HTTPException(404)
        return await super().get_response(path, scope)
