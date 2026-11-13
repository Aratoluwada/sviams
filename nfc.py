"""Role B: RC522 card reader over SPI. Not built yet.

Contract (guide section 2.3):
  read_uid(timeout) -> the card UID as uppercase hex with no spaces, or None on
                       timeout or reader error. Never raise into Flask.
Power the RC522 from 3.3 V only. Never 5 V.
"""


def read_uid(timeout):
    raise NotImplementedError
