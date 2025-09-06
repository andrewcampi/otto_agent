import os
import sys
import argparse
from dotenv import load_dotenv

from .core.cli import run_cli


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="otto", add_help=True)
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose tool call logging")
    args = parser.parse_args()
    return run_cli(verbose=bool(args.verbose))


if __name__ == "__main__":
    sys.exit(main())


