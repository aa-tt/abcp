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
           conda install -c conda-forge opencv numpy -y
    5. Run the script:
           python3 photo_sorter.py
    6. When prompted, enter the folder to analyze (drag the folder into Terminal to paste its path),
       e.g. /Users/<you>/Pictures/Trip, then type y to confirm.

Files are moved (not copied) into subfolders of the chosen folder; test on a copy first.
"""
import hashlib
import os
import shutil

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

PIC_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4"}

ALIKE_DIR = "alike_pics"
NOT_PICS_DIR = "not_pics"
MOVING_DIR = "moving_pics"
OBJECT_DIR = "object_pics"


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
        self.face = cv2.CascadeClassifier(
            os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        )
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

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) > 0:
            return True

        people, weights = self.hog.detectMultiScale(img, winStride=(8, 8), padding=(8, 8), scale=1.05)
        return any(float(wt) > 0.5 for wt in np.ravel(weights)) if len(people) else False


def sort_folder(folder):
    files = sorted(
        f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))
    )
    seen_hashes = {}
    unique_pics = []
    counts = {ALIKE_DIR: 0, NOT_PICS_DIR: 0, MOVING_DIR: 0, OBJECT_DIR: 0}

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
            digest = file_hash(path)
            if digest in seen_hashes:
                print(f"Duplicate: {name} == {seen_hashes[digest]}")
                move_file(path, os.path.join(folder, ALIKE_DIR))
                counts[ALIKE_DIR] += 1
            else:
                seen_hashes[digest] = name
                unique_pics.append(path)

    if cv2 is None:
        print("opencv-python not installed; skipping human detection (object_pics).")
    else:
        detector = HumanDetector()
        for path in unique_pics:
            result = detector.has_human(path)
            if result is None:
                print(f"Could not read image: {os.path.basename(path)}")
            elif not result:
                move_file(path, os.path.join(folder, OBJECT_DIR))
                counts[OBJECT_DIR] += 1

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
