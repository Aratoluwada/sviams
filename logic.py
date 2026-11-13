"""Entry and exit rules (guide section 3.2). Only this file changes tag status."""
import re

import db

ADMIN_STATUSES = ("available", "lost", "out_of_service")


def clean_plate(raw):
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def clean_uid(raw):
    return re.sub(r"[^0-9A-F]", "", (raw or "").upper())


def _result(status, mode, plate, uid, message, transaction_id=None, overridden=False):
    return {
        "status": status,
        "mode": mode,
        "plate": plate,
        "uid": uid,
        "message": message,
        "transaction_id": transaction_id,
        "overridden": overridden,
    }


def _missing_input(mode, plate, uid):
    if not plate:
        return _result("NO PLATE", mode, plate, uid, "No plate read. Try again.")
    if not uid:
        return _result("NO CARD", mode, plate, uid, "No card read. Try again.")
    return None


def handle_entry(plate, uid):
    plate, uid = clean_plate(plate), clean_uid(uid)
    missing = _missing_input("entry", plate, uid)
    if missing:  # Not logged: the operator just retries.
        return missing

    # The tag change and its log row commit together or not at all.
    with db.transaction() as conn:
        tag = db.get_tag(uid, conn)
        status, message = "MISMATCH", "Card is not registered."
        if tag is not None:
            if tag["status"] == "available":
                db.set_tag(uid, "assigned", plate, conn)
                status, message = "ASSIGNED", "Card assigned to vehicle."
            elif tag["status"] == "assigned":
                if tag["plate"] == plate:
                    message = "This vehicle is already inside."
                else:
                    message = "Card is already assigned to another vehicle."
            else:
                message = "Card is lost or out of service."
        tx_id = db.log_transaction("entry", plate, uid, status, conn=conn)
    return _result(status, "entry", plate, uid, message, tx_id)


def handle_exit(plate, uid):
    plate, uid = clean_plate(plate), clean_uid(uid)
    missing = _missing_input("exit", plate, uid)
    if missing:
        return missing

    with db.transaction() as conn:
        tag = db.get_tag(uid, conn)
        if tag is not None and tag["status"] == "assigned" and tag["plate"] == plate:
            db.set_tag(uid, "available", None, conn)
            status, message = "MATCH", "Plate matches the card. Card returned."
        elif tag is not None and tag["status"] == "assigned":
            status, message = "MISMATCH", "Card belongs to a different plate."
        else:
            status, message = "MISMATCH", "Card is not assigned to any vehicle."
        tx_id = db.log_transaction("exit", plate, uid, status, conn=conn)
    return _result(status, "exit", plate, uid, message, tx_id)


def override(transaction_id, note):
    """Flag a mismatch as overridden, with a reason.

    Open decision (guide section 5): this only records the override. It does not
    change any tag, so a card left assigned must be released by an admin.
    """
    note = (note or "").strip()
    if not note:
        raise ValueError("A reason is required.")
    with db.transaction() as conn:
        tx = db.get_transaction(transaction_id, conn)
        if tx is None:
            raise ValueError("Transaction not found.")
        if tx["result"] != "MISMATCH":
            raise ValueError("Only a mismatch can be overridden.")
        if tx["overridden"]:
            raise ValueError("This transaction was already overridden.")
        db.mark_overridden(transaction_id, note, conn)
    return _result("MISMATCH", tx["type"], tx["plate_read"], tx["uid"],
                   "Override recorded.", transaction_id, True)


def register_tag(uid):
    """Add a new card to the pool. Returns False if it is already registered."""
    uid = clean_uid(uid)
    if not uid:
        raise ValueError("A card UID is required.")
    return db.add_tag(uid)


def admin_set_status(uid, status):
    """Admin change: available, lost or out_of_service. Never 'assigned'."""
    if status not in ADMIN_STATUSES:
        raise ValueError("Status must be one of: " + ", ".join(ADMIN_STATUSES))
    with db.transaction() as conn:
        db.set_tag(uid, status, None, conn)
        return db.get_tag(uid, conn)
