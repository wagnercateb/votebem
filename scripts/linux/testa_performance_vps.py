import time
import psutil
import platform
import subprocess
import os

def cpu_test():
    print("Testing CPU speed...")
    start = time.time()
    for i in range(1, 10_000_000):
        _ = i*i
    end = time.time()
    print(f"CPU test completed in {end - start:.2f} seconds\n")

def memory_test():
    print("Testing memory speed...")
    start = time.time()
    size = 100_000_000  # Adjust if too large
    big_list = [0] * size
    end = time.time()
    print(f"Memory allocation test completed in {end - start:.2f} seconds\n")
    del big_list

def disk_test():
    file_path = "test_file.bin"

    # Write test
    print("Testing disk write speed...")
    start = time.time()
    with open(file_path, "wb") as f:
        f.write(os.urandom(1024*1024*100))  # 100 MB
        f.flush()
        os.fsync(f.fileno())
    end = time.time()
    print(f"Disk write test completed in {end - start:.2f} seconds")

    # Read test
    print("Testing disk read speed...")
    start = time.time()
    with open(file_path, "rb") as f:
        _ = f.read()
    end = time.time()
    print(f"Disk read test completed in {end - start:.2f} seconds\n")

    # Clean up
    os.remove(file_path)

def network_test():
    print("Testing network speed (ping to Google DNS)...")
    response = subprocess.run(["ping", "-c", "4", "8.8.8.8"], capture_output=True, text=True)
    print(response.stdout)
    print()

def system_info():
    print("System Information:")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"CPU Cores: {psutil.cpu_count(logical=True)}")
    print(f"Total RAM: {round(psutil.virtual_memory().total / (1024**3), 2)} GB")
    print()

if __name__ == "__main__":
    system_info()
    cpu_test()
    memory_test()
    disk_test()
    network_test()
    print("VPS performance test completed.")
