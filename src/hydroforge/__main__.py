"""Allow running the package as: python -m hydroforge"""

from .cli import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
