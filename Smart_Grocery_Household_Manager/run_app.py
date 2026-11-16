from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'app'))
from main import GroceryApp

if __name__ == '__main__':
    GroceryApp().mainloop()
