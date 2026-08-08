"""Allow `python -m trackpod` to run the CLI."""

import sys

from trackpod.cli import main

if __name__ == "__main__":
    sys.exit(main())
