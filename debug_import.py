import sys
import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

print("Starting debug...")
try:
    import database
    print("database imported.")
    import utils
    print("utils imported.")
    import ocr_service
    print("ocr_service imported.")
    import normalizer
    print("normalizer imported.")
    import classifier
    print("classifier imported.")
    import indexer
    print("indexer imported.")
except SystemExit:
    print("A module called sys.exit().")
except Exception as e:
    print(f"Import failed: {e}")
