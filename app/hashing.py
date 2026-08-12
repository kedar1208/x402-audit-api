import hashlib
import json


def canonical_json(obj: dict) -> bytes:
    """Deterministic encoding so the same logical payload always hashes the
    same way regardless of key ordering (sorted keys, no extra whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(obj: dict) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()
