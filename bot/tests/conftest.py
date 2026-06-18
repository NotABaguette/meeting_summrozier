import pathlib
import sys

# Make the repository root importable so `import bot.helpers` works.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
