import sys

from .shell.app import main

raise SystemExit(main(sys.argv[1:]))
