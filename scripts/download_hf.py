from __future__ import annotations

import argparse

from huggingface_hub import hf_hub_download, snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser(description="Download HF model to local dir")
    parser.add_argument("--repo", required=True, help="Hugging Face repo id")
    parser.add_argument("--out", required=True, help="Local output directory")
    parser.add_argument("--file", help="Single file to download (optional)")
    args = parser.parse_args()

    if args.file:
        hf_hub_download(
            repo_id=args.repo,
            filename=args.file,
            local_dir=args.out,
        )
        return
    snapshot_download(repo_id=args.repo, local_dir=args.out, local_dir_use_symlinks=False)


if __name__ == "__main__":
    main()
