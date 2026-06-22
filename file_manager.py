import os.path

REPORT_FILE = r'report.txt'

def report_print(*args, sep=" ", end="\n", file=None, flush=False):
    message = sep.join(str(arg) for arg in args)
    print(*args, sep=sep, end=end, file=file, flush=flush)

    os.makedirs(os.path.dirname(REPORT_FILE) or ".", exist_ok=True)

    with open(REPORT_FILE, "a", encoding="utf-8") as f:
        f.write(message + end)
        
def cleanup_worker_artifacts(artifact_files: dict):
    deleted = 0
    missing = 0
    for _, file_list in artifact_files.items():
        for path in file_list:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    deleted += 1
                else:
                    missing += 1
            except Exception as e:
                print(f"[Cleanup error] {path}: {e}")
    print(f"[Cleanup] Deleted: {deleted}, Missing: {missing}")