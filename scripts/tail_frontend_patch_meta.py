from pathlib import Path


root = Path(__file__).resolve().parent
text = (root / "frontend_patch_meta.txt").read_text(encoding="utf-8")
(root / "frontend_patch_meta_tail.txt").write_text(text[-12000:], encoding="utf-8")
