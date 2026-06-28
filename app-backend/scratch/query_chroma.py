import os
import sys
import argparse

# Add parent directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure stdout and stderr to use UTF-8 to prevent encoding errors on Windows
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import chromadb
    from core.config import settings
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please make sure you are running this script from the project virtual environment.")
    sys.exit(1)


def format_table(headers, rows):
    """Format rows as a neat text table if tabulate is not available."""
    try:
        from tabulate import tabulate
        return tabulate(rows, headers=headers, tablefmt="grid")
    except ImportError:
        # Fallback to custom formatting
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))
        
        # Build lines
        sep = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
        header_line = "|" + "|".join([f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)]) + "|"
        
        lines = [sep, header_line, sep]
        for row in rows:
            row_line = "|" + "|".join([f" {str(val):<{col_widths[i]}} " for i, val in enumerate(row)]) + "|"
            lines.append(row_line)
        lines.append(sep)
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Query and inspect ChromaDB collection data.")
    parser.add_argument(
        "collection", 
        nargs="?", 
        help="Collection name (e.g. 'textbook_vec_1') or Textbook ID (e.g. '1'). If empty, lists all collections."
    )
    parser.add_argument(
        "-l", "--limit", 
        type=int, 
        default=10, 
        help="Number of items to retrieve (default: 10)"
    )
    parser.add_argument(
        "-o", "--offset", 
        type=int, 
        default=-1, 
        help="Offset to query from. If -1, fetches the LATEST items (default: -1, i.e. the last 'limit' items)"
    )
    parser.add_argument(
        "--first", 
        action="store_true", 
        help="Fetch the FIRST items instead of the LATEST items (overrides offset to 0)"
    )

    args = parser.parse_args()

    db_path = os.path.abspath(settings.CHROMADB_PATH)
    print(f"Connecting to ChromaDB at: {db_path}")

    if not os.path.exists(db_path):
        print(f"Warning: ChromaDB path '{db_path}' does not exist yet. Please check config or upload some textbooks first.")
        sys.exit(1)

    try:
        client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
    except Exception as e:
        print(f"Failed to connect to ChromaDB: {e}")
        sys.exit(1)

    try:
        collections = client.list_collections()
    except Exception as e:
        print(f"Failed to list collections: {e}")
        sys.exit(1)

    if not collections:
        print("No collections found in ChromaDB.")
        return

    # If no collection is specified, list all and show usage
    if not args.collection:
        print("\n=== Available Collections in ChromaDB ===")
        headers = ["Collection Name", "Estimated Count"]
        rows = []
        for col in collections:
            rows.append([col.name, col.count()])
        print(format_table(headers, rows))
        print("\nUsage example:")
        print("  python scratch/query_chroma.py <collection_name_or_textbook_id>")
        print("  python scratch/query_chroma.py 1 --limit 5")
        return

    # Resolve collection name
    col_name = args.collection
    if col_name.isdigit():
        col_name = f"textbook_vec_{col_name}"

    print(f"\nFetching collection: '{col_name}'...")
    try:
        collection = client.get_collection(name=col_name)
    except Exception as e:
        print(f"Error: Collection '{col_name}' not found. ({e})")
        print("\nAvailable collections:")
        for col in collections:
            print(f" - {col.name}")
        sys.exit(1)

    total_count = collection.count()
    print(f"Total documents in '{col_name}': {total_count}")

    if total_count == 0:
        print("This collection is empty.")
        return

    # Calculate offset
    limit = args.limit
    if args.first:
        offset = 0
        order_desc = "First (earliest)"
    elif args.offset >= 0:
        offset = args.offset
        order_desc = f"Offset {offset}"
    else:
        # Fetch the last `limit` items
        offset = max(0, total_count - limit)
        order_desc = "Latest (recent)"

    print(f"Retrieving {limit} items ({order_desc}) starting from index {offset}...")

    try:
        # ChromaDB .get() retrieves items by limit & offset
        results = collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"]
        )
    except Exception as e:
        print(f"Failed to retrieve items from collection: {e}")
        sys.exit(1)

    ids = results.get("ids", [])
    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])

    if not ids:
        print("No records found in this range.")
        return

    print(f"\n--- Results ({len(ids)} items) ---")
    headers = ["ID", "Page", "Text Snippet (First 80 chars)", "Metadata Details"]
    rows = []
    
    for i in range(len(ids)):
        item_id = ids[i]
        doc = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if (metadatas and i < len(metadatas)) else {}
        
        # Clean doc snippet
        snippet = doc.replace("\n", " ").strip()
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
            
        page = meta.get("page_number", "N/A")
        
        # Format metadata (excluding page number to avoid redundancy)
        meta_display = ", ".join([f"{k}:{v}" for k, v in meta.items() if k != "page_number"])
        if len(meta_display) > 50:
            meta_display = meta_display[:47] + "..."

        rows.append([item_id, page, snippet, meta_display])

    print(format_table(headers, rows))


if __name__ == "__main__":
    main()
