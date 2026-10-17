"""Download pinned Leaflet assets so map code does not depend on a CDN at runtime."""
from pathlib import Path
import requests


def main():
    destination = Path(__file__).resolve().parents[2] / "frontend" / "vendor" / "leaflet"
    files = ["dist/leaflet.js", "dist/leaflet.css", "dist/images/marker-icon.png", "dist/images/marker-icon-2x.png", "dist/images/marker-shadow.png", "dist/images/layers.png", "dist/images/layers-2x.png", "LICENSE"]
    for name in files:
        response = requests.get(f"https://unpkg.com/leaflet@1.9.4/{name}", timeout=30)
        response.raise_for_status()
        relative = name.removeprefix("dist/")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
    print(f"Leaflet 1.9.4: downloaded {len(files)} public assets")


if __name__ == "__main__":
    main()
