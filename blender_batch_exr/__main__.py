"""Start the GUI with no arguments; otherwise use the headless CLI."""
from .cli import main

if __name__ == '__main__':
    raise SystemExit(main())
