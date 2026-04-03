"""DEPRECATED — Legacy SQLite-only migration script.

This script was used to add ERP reference fields to an existing SQLite
database.  Schema changes are now managed exclusively through Alembic
migrations.  The columns added by this script are already included in
the initial Alembic migration (001_initial_schema).

To apply schema changes, run:

    alembic upgrade head
"""

import sys


def main() -> None:
    print(
        "This script is deprecated.\n"
        "Schema changes are now managed via Alembic migrations.\n"
        "Run:  alembic upgrade head"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
