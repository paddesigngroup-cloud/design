from pathlib import Path

ROOT = Path(__file__).parent
INCLUDE = [
    "2d/src",
    "2d/public",
]
EXCLUDE_DIRS = {".venv", "node_modules", ".git", "__pycache__", "dist", "build"}
EXCLUDE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".glb", ".zip", ".exe"}

def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.suffix.lower() in EXCLUDE_EXT:
        return True
    # فایل‌های خیلی بزرگ رو رد کن
    try:
        if path.stat().st_size > 200_000:  # 200KB
            return True
    except:
        return True
    return False

out = []
for rel in INCLUDE:
    base = ROOT / rel
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if p.is_dir() or should_skip(p):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except:
            continue
        out.append(f"\n\n--- FILE: {p.relative_to(ROOT)} ---\n{text}")

(Path("PROJECT_DUMP.txt")).write_text("".join(out), encoding="utf-8")
print("Wrote PROJECT_DUMP.txt")