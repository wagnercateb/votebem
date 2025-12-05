"""
Management command: chroma_dump

Purpose:
- Export a ChromaDB collection from a local persistent client to a JSONL file
  containing ids, documents, metadatas, and embeddings.

Why:
- Enables copying embeddings from local to remote environments without re‑embedding.
- The JSONL format is line‑oriented and easy to transfer and import.

Usage examples:
- Dump default dev path and collection:
  python manage.py chroma_dump --path "C:/path/to/chroma" --collection "rag_docs" --out "C:/tmp/rag_docs_dump.jsonl"

Notes:
- This command reads data in pages to avoid excessive memory usage.
- The output file can be transferred to a remote server and imported with chroma_load.
"""

from django.core.management.base import BaseCommand, CommandError
import os
import json


class Command(BaseCommand):
    help = "Dump a ChromaDB collection (ids, documents, metadatas, embeddings) to a JSONL file."

    def add_arguments(self, parser):
        parser.add_argument("--path", dest="path", required=True, help="Chroma persistent path directory")
        parser.add_argument("--collection", dest="collection", required=True, help="Chroma collection name to export")
        parser.add_argument("--out", dest="out", required=True, help="Output JSONL file path")
        parser.add_argument("--page_size", dest="page_size", type=int, default=1000, help="Page size for batched reads")

    def handle(self, *args, **options):
        path = options["path"]
        collection_name = options["collection"]
        out_path = options["out"]
        page_size = int(options["page_size"]) or 1000

        # Basic validation of path and write target
        if not os.path.isdir(path):
            raise CommandError(f"Chroma path not found or not a directory: {path}")

        # Ensure output directory exists
        out_dir = os.path.dirname(out_path) or "."
        os.makedirs(out_dir, exist_ok=True)

        try:
            import chromadb
        except Exception as e:
            raise CommandError(f"chromadb not installed: {e}")

        # Create persistent client bound to provided path
        try:
            client = chromadb.PersistentClient(path=path)
        except Exception as e:
            raise CommandError(f"Failed to initialize PersistentClient at '{path}': {e}")

        # Get collection
        try:
            coll = client.get_collection(collection_name)
        except Exception as e:
            raise CommandError(f"Failed to open collection '{collection_name}': {e}")

        # Write JSONL with batched reads
        total = 0
        offset = 0
        self.stdout.write(self.style.WARNING(f"Exporting collection '{collection_name}' from '{path}' to '{out_path}'"))
        with open(out_path, "w", encoding="utf-8") as f:
            while True:
                try:
                    batch = coll.get(
                        include=["documents", "metadatas", "embeddings"],
                        limit=page_size,
                        offset=offset,
                    )
                except Exception as e:
                    raise CommandError(f"Error reading collection batch at offset {offset}: {e}")

                ids = batch.get("ids") or []
                docs = batch.get("documents") or []
                metas = batch.get("metadatas") or []
                embs = batch.get("embeddings") or []

                if not ids:
                    break

                for i in range(len(ids)):
                    rec = {
                        "id": ids[i],
                        "document": docs[i] if i < len(docs) else None,
                        "metadata": metas[i] if i < len(metas) else None,
                        "embedding": embs[i] if i < len(embs) else None,
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    total += 1

                offset += len(ids)
                self.stdout.write(self.style.NOTICE(f"Exported {total} items…"))

        self.stdout.write(self.style.SUCCESS(f"Export complete: {total} items written to {out_path}"))