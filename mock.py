"""Fake plate and card readings. TEMPORARY: delete once Step 7 connects real hardware."""
import random

import db

SAMPLE_PLATES = ["ABC123XY", "LSR456KJ", "KJA789AA", "FST321BD", "EKY654GH"]
DEMO_UIDS = ["A1B2C3D4", "B2C3D4E5", "C3D4E5F6", "D4E5F6A7"]


def fake_reading(mode):
    """Return (plate, uid) for a demo. On exit, usually a vehicle that is really inside."""
    tags = db.list_tags()
    if mode == "exit":
        inside = [t for t in tags if t["status"] == "assigned"]
        if inside:
            tag = random.choice(inside)
            if random.random() < 0.75:
                return tag["plate"], tag["uid"]
            others = [p for p in SAMPLE_PLATES if p != tag["plate"]]
            return random.choice(others), tag["uid"]
    free = [t["uid"] for t in tags if t["status"] == "available"]
    uid = random.choice(free) if free else random.choice(DEMO_UIDS)
    return random.choice(SAMPLE_PLATES), uid
