"""
CLI en sèrie per processar una contingència individual de la base de dades.

La lògica de càlcul viu a ``contingency.py`` (mòdul compartit amb
``pycompss_main.py``). Aquest script només fa de CLI: rep un ``contingency_id``,
crida ``contingency.process_contingency`` (load → calculate → save) i imprimeix
el resultat.

Ús:
    python 2.process.py <contingency_id>
"""

import argparse

from contingency import process_contingency


def main():
    parser = argparse.ArgumentParser(description="Process one contingency from the database.")
    parser.add_argument(
        "contingency_id",
        type=int,
        nargs="?",
        help="Primary key of the contingency to process",
    )
    args = parser.parse_args()

    if args.contingency_id is None:
        parser.error("contingency_id is required")

    result = process_contingency(args.contingency_id)
    print(result)


if __name__ == "__main__":
    main()
