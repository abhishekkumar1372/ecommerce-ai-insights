"""Create the AI tables and build the retrieval index.  Usage: python -m ecom.ai.setup"""
from pathlib import Path

from ecom.ai import db, retrieval
from ecom.config import ROOT


def main() -> None:
    with db.connect() as conn:
        conn.execute(Path(ROOT / "db/init/02_ai.sql").read_text())
    print(f"Indexed {retrieval.index()} knowledge entries into ai.knowledge")


if __name__ == "__main__":
    main()
