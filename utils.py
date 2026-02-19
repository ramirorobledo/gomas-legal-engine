import hashlib
import time
import os
import shutil
import logging

def calculate_file_hash(filepath: str) -> str:
    """Calculates SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def wait_for_file_stabilization(filepath: str, stability_duration: int = 3, check_interval: int = 1) -> bool:
    """
    Waits for a file size to remain constant for a specified duration.
    Returns True if stabilized, False if it times out or disappears.
    """
    if not os.path.exists(filepath):
        return False

    last_size = -1
    stable_start = None
    
    # Wait max 60 seconds for stabilization
    max_wait = 60
    start_wait = time.time()

    while time.time() - start_wait < max_wait:
        if not os.path.exists(filepath):
            return False
            
        try:
            current_size = os.path.getsize(filepath)
        except OSError:
            # File might be locked
            time.sleep(check_interval)
            continue

        if current_size == last_size:
            if stable_start is None:
                stable_start = time.time()
            elif time.time() - stable_start >= stability_duration:
                return True
        else:
            last_size = current_size
            stable_start = None
        
        time.sleep(check_interval)
    
    return False

def safe_move(src: str, dst: str):
    """Moves a file, overwriting destination if exists, handling Windows locks."""
    try:
        shutil.move(src, dst)
    except OSError as e:
        # Simple retry logic for Windows
        time.sleep(1)
        shutil.move(src, dst)
