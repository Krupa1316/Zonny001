import secrets
import json
from pathlib import Path

KEY_FILE = Path("key.json")

def create_key():
    return "sk-local-" + secrets.token_hex(16)

def save_key(key):
    if KEY_FILE.exists() and KEY_FILE.read_text().strip():
        keys = json.loads(KEY_FILE.read_text())
    else:
        keys = []

    keys.append(key)
    KEY_FILE.write_text(json.dumps(keys, indent=2))

if __name__ == "__main__":
    key = create_key()
    save_key(key)
    print("Ner API key:")
    print(key)

