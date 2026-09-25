"""Console executable: never launches the GUI, even without inputs."""
import sys
from blender_batch_exr.cli import main

if __name__ == '__main__':
    raise SystemExit(main(['--headless', *sys.argv[1:]]))
