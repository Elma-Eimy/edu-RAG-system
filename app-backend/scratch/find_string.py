import os

def search_text_in_files(directory, search_query):
    for root, dirs, files in os.walk(directory):
        if '.venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith(('.py', '.yaml', '.yml', '.env', '.json', '.md', '.txt')):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if search_query in line:
                                print(f"Found in {path}:{line_num} | {line.strip()}")
                except Exception:
                    pass

if __name__ == "__main__":
    search_text_in_files('g:\\WebProject\\app-backend', 'apitest')
