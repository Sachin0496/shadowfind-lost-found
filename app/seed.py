"""Seed the ShadowFind database with demo accounts and item reports.

Run once before the first `flask run`, or any time you want to reset the demo:

    python seed.py            (keeps an existing database)
    python seed.py --reset    (deletes every table first)
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2

import db
import vision

import os
DATA = Path(os.environ.get("SHADOWFIND_DATA", Path(__file__).resolve().parent.parent / "instance"))
UPLOADS = DATA / "uploads"
DB_PATH = DATA / "shadowfind.sqlite3"

PASSWORD = "shadow123"

STUDENTS = [
    ("Ananya R", "ananya@college.edu", "CSE"),
    ("Rahul M", "rahul@college.edu", "ECE"),
    ("Priya K", "priya@college.edu", "IT"),
    ("Karthik S", "karthik@college.edu", "MECH"),
]

# (owner index, type, title, category, kind, colour, place, date, description)
ITEMS = [
    (0, "lost",  "Blue Nike backpack",   "Bag",      "bag",      "blue",   "Canteen",            "2026-10-12",
     "Blue Nike backpack with a white swoosh, a broken left zip and a small green dinosaur keychain."),
    (1, "found", "Blue backpack",        "Bag",      "bag",      "blue",   "Physics Lab 2",      "2026-10-14",
     "Found a blue backpack after the lab session. Slightly worn, white logo on the front."),
    (2, "found", "Laptop bag",           "Bag",      "bag",      "grey",   "Central Library",    "2026-10-15",
     "Dark laptop bag left near the reading room. Has a side pocket with a padlock."),
    (0, "lost",  "Casio F-91W watch",    "Watch",    "watch",    "black",  "Sports ground",      "2026-10-09",
     "Black Casio digital watch, resin strap, small scratch on the glass."),
    (3, "found", "Digital watch",        "Watch",    "watch",    "black",  "Sports ground",      "2026-10-10",
     "Found a black digital watch near the basketball court."),
    (1, "lost",  "Steel water bottle",   "Bottle",   "bottle",   "grey",   "Mechanical Block",   "2026-10-11",
     "One litre steel bottle with a blue cap and a dent near the base."),
    (2, "found", "Water bottle",         "Bottle",   "bottle",   "grey",   "Canteen",            "2026-10-14",
     "Steel bottle with a coloured cap, found on a canteen table."),
    (3, "lost",  "Black umbrella",       "Umbrella", "umbrella", "black",  "Bus stop",           "2026-10-06",
     "Compact black umbrella with a wooden handle."),
    (1, "found", "Umbrella",             "Umbrella", "umbrella", "black",  "Main gate",          "2026-10-07",
     "Black folding umbrella left at the main gate."),
    (2, "lost",  "White helmet",         "Helmet",   "helmet",   "white",  "Parking area",       "2026-10-05",
     "White full-face helmet with a clear visor and a red stripe."),
    (3, "found", "Helmet",               "Helmet",   "helmet",   "white",  "Parking area",       "2026-10-06",
     "White helmet found beside the two-wheeler parking."),
]


def main(reset: bool = False) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)

    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    if reset and UPLOADS.exists():
        shutil.rmtree(UPLOADS)
        UPLOADS.mkdir(parents=True)

    db.init_db(DB_PATH)
    conn = db.connect(DB_PATH)

    if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]:
        print(f"Database already has data at {DB_PATH}. Use --reset to rebuild.")
        return

    ids = [db.create_student(conn, name, email, PASSWORD, dept)
           for name, email, dept in STUDENTS]

    made = 0
    for owner, type_, title, category, kind, colour, place, seen_on, desc in ITEMS:
        # a distinct seed per report, so the two photos of the same item are
        # genuinely different pictures rather than identical renders
        img = vision.make_sample(colour, kind, seed=1000 + owner * 31 + made * 17)
        token = f"seed_{kind}_{colour}_{made}"
        photo = f"{token}.jpg"
        overlay = f"{token}_shadow.jpg"
        cv2.imwrite(str(UPLOADS / photo), img)

        sil = vision.extract_shadow(img)
        tinted = img.copy()
        tinted[sil.mask > 0] = (0.45 * tinted[sil.mask > 0]
                                + 0.55 * __import__("numpy").array([40, 90, 170])).astype("uint8")
        cv2.imwrite(str(UPLOADS / overlay), tinted)

        db.create_item(conn, student_id=ids[owner], title=title, type_=type_,
                       category=category, description=desc, place=place,
                       seen_on=seen_on, photo=photo, overlay=overlay,
                       descriptor=sil.descriptor, shadow_iou=sil.iou)
        made += 1

    print(f"Seeded {len(ids)} students and {made} items into {DB_PATH}")
    print(f"Log in with any of: " + ", ".join(e for _, e, _ in STUDENTS))
    print(f"Password: {PASSWORD}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete and rebuild the database")
    main(**vars(ap.parse_args()))
