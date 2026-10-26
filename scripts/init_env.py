"""Create local environment without printing secrets. Run with the backend venv Python."""

import secrets
from pathlib import Path
from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[1]
target = root / "backend" / ".env"
if target.exists():
    raise SystemExit("backend/.env already exists; refusing to overwrite it")
content = (root / "backend" / ".env.example").read_text()
content = content.replace("replace_with_at_least_32_random_characters", secrets.token_urlsafe(48))
content = content.replace("replace_with_valid_fernet_key", Fernet.generate_key().decode())
target.write_text(content, encoding="utf-8")
print("Created backend/.env. Edit database credentials and bootstrap admin email before starting.")
