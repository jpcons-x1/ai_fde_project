"""Rebuild the UnderCover database from data/: uv run -m backend.seed"""

from backend.db import database_path, seed


def main() -> None:
    counts = seed()
    loaded = ", ".join(f"{count} {name}" for name, count in counts.items())
    print(f"Loaded {loaded} into {database_path()}")


if __name__ == "__main__":
    main()
