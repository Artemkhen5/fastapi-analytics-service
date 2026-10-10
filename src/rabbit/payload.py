import hashlib
import json


def calculate_payload_hash(body: bytes) -> str:
    payload = json.loads(body)
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
