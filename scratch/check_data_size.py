import os

data_dir = "data"
for item in sorted(os.listdir(data_dir)):
    p = os.path.join(data_dir, item)
    if os.path.isdir(p):
        total_size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
        file_count = sum(len(fs) for _, _, fs in os.walk(p))
        print(f"{item:<30}: {total_size / (1024 * 1024):10.2f} MB ({file_count} files)")
