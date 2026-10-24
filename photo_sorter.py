"""Sort a folder's files into alike_pics, not_pics, moving_pics and object_pics.

How to run on macOS (Terminal):
    1. Check Python 3 is installed (install with `brew install python` or from python.org):
           python3 --version
    2. Go to the folder containing this script:
           cd /path/to/abcp
    3. (Optional) Create and activate a virtual environment:
           python3 -m venv .venv
           source .venv/bin/activate
    4. Install dependencies:
           pip3 install opencv-python numpy
       Or, with conda instead of pip/venv:
           conda create -n photo_sorter python=3.11 -y
           conda activate photo_sorter
           conda install -c conda-forge numpy pip -y
           pip install opencv-python
       (conda-forge's "opencv" package may lack cv2.data/CascadeClassifier; use pip's opencv-python.)
    5. Run the script:
           python3 photo_sorter.py
    6. When prompted, enter the folder to analyze (drag the folder into Terminal to paste its path),
       e.g. /Users/<you>/Pictures/Trip, then type y to confirm.

Files are moved (not copied) into subfolders of the chosen folder; test on a copy first.

SQLite:
    No install needed: sqlite3 ships with Python (python.org, Homebrew and conda builds).
    Verify:  python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
    Hashes are stored in <chosen folder>/.photo_hashes.db while running; if a run is interrupted,
    just rerun on the same folder to resume. The file is deleted after a successful run.
    Optional, inspect it with the sqlite3 CLI preinstalled on macOS:
           sqlite3 "/path/to/folder/.photo_hashes.db" "SELECT hash, COUNT(*) FROM photos GROUP BY hash HAVING COUNT(*) > 1;"
    To start over from scratch, delete it:  rm "/path/to/folder/.photo_hashes.db"
"""
import hashlib
import os
import shutil
import sqlite3

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

if cv2 is not None and not hasattr(cv2, "HOGDescriptor"):
    # An empty leftover cv2 folder or a local cv2.py can shadow the real OpenCV
    print(f"Broken OpenCV import, loaded from: {getattr(cv2, '__file__', None) or list(getattr(cv2, '__path__', []))}")
    cv2 = None

PIC_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4"}

ALIKE_DIR = "alike_pics"
NOT_PICS_DIR = "not_pics"
MOVING_DIR = "moving_pics"
OBJECT_DIR = "object_pics"
DB_NAME = ".photo_hashes.db"


def file_hash(path, chunk_size=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def move_file(src, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    name, ext = os.path.splitext(os.path.basename(src))
    dest = os.path.join(dest_dir, name + ext)
    counter = 1
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{name}_{counter}{ext}")
        counter += 1
    shutil.move(src, dest)
    return dest


class HumanDetector:
    def __init__(self):
        self.face = None
        try:
            face = cv2.CascadeClassifier(
                os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            )
            if not face.empty():
                self.face = face
        except AttributeError:
            pass
        if self.face is None:
            print("Face detector unavailable in this OpenCV build; using person detector only.")
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def has_human(self, path):
        # np.fromfile + imdecode handles non-ASCII Windows paths, unlike cv2.imread
        img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        scale = 800 / max(h, w)
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))

        if self.face is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self.face.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            if len(faces) > 0:
                return True

        people, weights = self.hog.detectMultiScale(img, winStride=(8, 8), padding=(8, 8), scale=1.05)
        return any(float(wt) > 0.5 for wt in np.ravel(weights)) if len(people) else False


def open_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS photos (
               name  TEXT PRIMARY KEY,
               size  INTEGER NOT NULL,
               mtime REAL NOT NULL,
               hash  TEXT NOT NULL,
               human INTEGER
           )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON photos(hash)")
    return conn


def sort_folder(folder):
    files = sorted(
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and not f.startswith(".")
    )
    counts = {ALIKE_DIR: 0, NOT_PICS_DIR: 0, MOVING_DIR: 0, OBJECT_DIR: 0}

    # Pass 0: separate videos and non-pictures
    pics = []
    for name in files:
        path = os.path.join(folder, name)
        ext = os.path.splitext(name)[1].lower()
        if ext in VIDEO_EXTS:
            move_file(path, os.path.join(folder, MOVING_DIR))
            counts[MOVING_DIR] += 1
        elif ext not in PIC_EXTS:
            move_file(path, os.path.join(folder, NOT_PICS_DIR))
            counts[NOT_PICS_DIR] += 1
        else:
            pics.append(name)

    db_path = os.path.join(folder, DB_NAME)
    conn = open_db(db_path)
    try:
        # Pass 1: hash every picture into SQLite (skips files already hashed and unchanged)
        conn.execute("CREATE TEMP TABLE present (name TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO present VALUES (?)", ((n,) for n in pics))
        conn.execute("DELETE FROM photos WHERE name NOT IN (SELECT name FROM present)")
        known = {
            name: (size, mtime)
            for name, size, mtime in conn.execute("SELECT name, size, mtime FROM photos")
        }
        total = len(pics)
        for i, name in enumerate(pics, 1):
            path = os.path.join(folder, name)
            st = os.stat(path)
            if known.get(name) != (st.st_size, st.st_mtime):
                conn.execute(
                    "INSERT OR REPLACE INTO photos (name, size, mtime, hash, human) VALUES (?, ?, ?, ?, NULL)",
                    (name, st.st_size, st.st_mtime, file_hash(path)),
                )
            if i % 200 == 0 or i == total:
                conn.commit()
                print(f"\rHashing: {i}/{total}", end="", flush=True)
        print()

        # Pass 2: identical hashes => alike; keep the first file per hash, move the rest
        dupes = conn.execute(
            """SELECT name, hash FROM photos
               WHERE hash IN (SELECT hash FROM photos GROUP BY hash HAVING COUNT(*) > 1)
               ORDER BY hash, name"""
        ).fetchall()
        kept = {}
        for name, digest in dupes:
            if digest not in kept:
                kept[digest] = name
                continue
            print(f"Duplicate: {name} == {kept[digest]}")
            move_file(os.path.join(folder, name), os.path.join(folder, ALIKE_DIR))
            conn.execute("DELETE FROM photos WHERE name = ?", (name,))
            counts[ALIKE_DIR] += 1
        conn.commit()

        # Pass 3: move unique pictures without humans to object_pics (resumable via 'human' column)
        if cv2 is None:
            print("opencv-python not installed; skipping human detection (object_pics).")
        else:
            detector = HumanDetector()
            pending = [r[0] for r in conn.execute("SELECT name FROM photos WHERE human IS NULL ORDER BY name")]
            for i, name in enumerate(pending, 1):
                path = os.path.join(folder, name)
                result = detector.has_human(path)
                if result is None:
                    print(f"\nCould not read image: {name}")
                    conn.execute("UPDATE photos SET human = -1 WHERE name = ?", (name,))
                elif result:
                    conn.execute("UPDATE photos SET human = 1 WHERE name = ?", (name,))
                else:
                    move_file(path, os.path.join(folder, OBJECT_DIR))
                    conn.execute("DELETE FROM photos WHERE name = ?", (name,))
                    counts[OBJECT_DIR] += 1
                if i % 50 == 0 or i == len(pending):
                    conn.commit()
                    print(f"\rHuman detection: {i}/{len(pending)}", end="", flush=True)
            print()
    finally:
        conn.commit()
        conn.close()

    # All passes finished, so the temporary database is no longer needed
    os.remove(db_path)

    print("\nSummary:")
    for dir_name, count in counts.items():
        print(f"  {dir_name}: {count} file(s)")


def main():
    folder = input("Enter the folder path to analyze: ").strip().strip('"').strip("'")
    # macOS Terminal drag-and-drop escapes spaces as "\ "
    folder = folder.replace("\\ ", " ")
    folder = os.path.abspath(os.path.expanduser(folder))
    if not os.path.isdir(folder):
        print(f"Not a valid directory: {folder}")
        return
    confirm = input(f"Files in '{folder}' will be moved into subfolders. Continue? (y/n): ")
    if confirm.strip().lower() != "y":
        print("Aborted.")
        return
    sort_folder(folder)


if __name__ == "__main__":
    main()
