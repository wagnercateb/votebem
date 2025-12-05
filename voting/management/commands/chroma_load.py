"""
Management command: chroma_load

Purpose:
- Import a JSONL dump (created by chroma_dump) into a ChromaDB collection
  on a (persistent) client. This restores ids, documents, metadatas, embeddings
  without recomputing embeddings, ensuring a fast migration from local to remote.

Usage examples:
- Load into a remote path and collection:
  python manage.py chroma_load --path "/srv/chroma" --collection "rag_docs" --in "/srv/import/rag_docs_dump.jsonl"

Notes:
- Skips records whose ids already exist (to avoid duplicates). If you want to
  overwrite, delete the collection first or implement an update policy.
- Reads JSONL line-by-line, batching adds to improve throughput.
"""

from django.core.management.base import BaseCommand, CommandError
import os
import json


class Command(BaseCommand):
    help = "Load a JSONL dump into a ChromaDB collection (ids, documents, metadatas, embeddings)."

    def add_arguments(self, parser):
        parser.add_argument("--path", dest="path", required=True, help="Chroma persistent path directory")
        parser.add_argument("--collection", dest="collection", required=True, help="Chroma collection name to import into")
        parser.add_argument("--in", dest="in_path", required=True, help="Input JSONL file path")
        parser.add_argument("--batch", dest="batch", type=int, default=1000, help="Batch size for adds")

    def handle(self, *args, **options):
        path = options["path"]
        collection_name = options["collection"]
        in_path = options["in_path"]
        batch_size = int(options["batch"]) or 1000

        if not os.path.isdir(path):
            raise CommandError(f"Chroma path not found or not a directory: {path}")

        if not os.path.isfile(in_path):
            raise CommandError(f"Input JSONL file not found: {in_path}")

        try:
            import chromadb
        except Exception as e:
            raise CommandError(f"chromadb not installed: {e}")

        # Initialize persistent client and collection
        try:
            client = chromadb.PersistentClient(path=path)
        except Exception as e:
            raise CommandError(f"Failed to initialize PersistentClient at '{path}': {e}")

        try:
            # Use get_or_create in case the collection is new
            coll = client.get_or_create_collection(name=collection_name)
        except Exception as e:
            raise CommandError(f"Failed to open/create collection '{collection_name}': {e}")

        self.stdout.write(self.style.WARNING(f"Importing into collection '{collection_name}' at '{path}' from '{in_path}'"))

        ids_batch = []
        docs_batch = []
        metas_batch = []
        embs_batch = []
        total = 0

        def flush_batch():
            nonlocal ids_batch, docs_batch, metas_batch, embs_batch, total
            if not ids_batch:
                return
            try:
                coll.add(ids=ids_batch, documents=docs_batch, metadatas=metas_batch, embeddings=embs_batch)
                total += len(ids_batch)
            except Exception as e:
                # If IDs exist, attempt to add only new ones
                # We handle duplicates by filtering out existing IDs
                try:
                    # Determine which IDs exist already
                    existing = set()
                    try:
                        res = coll.get(ids=ids_batch)
                        for ex_id in res.get("ids") or []:
                            existing.add(ex_id)
                    except Exception:
                        existing = set()

                    new_ids = []
                    new_docs = []
                    new_metas = []
                    new_embs = []
                    for i, _id in enumerate(ids_batch):
                        if _id in existing:
                            continue
                        new_ids.append(_id)
                        new_docs.append(docs_batch[i])
                        new_metas.append(metas_batch[i])
                        new_embs.append(embs_batch[i])
                    if new_ids:
                        coll.add(ids=new_ids, documents=new_docs, metadatas=new_metas, embeddings=new_embs)
                        total += len(new_ids)
                except Exception as e2:
                    raise CommandError(f"Failed to add batch (after duplicate handling): {e}; {e2}")
            finally:
                ids_batch = []
                docs_batch = []
                metas_batch = []
                embs_batch = []

        # Stream JSONL and batch up inserts
        with open(in_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception as e:
                    raise CommandError(f"Invalid JSON line: {e}\nLine: {line[:120]}…")
                _id = rec.get("id")
                doc = rec.get("document")
                meta = rec.get("metadata")
                emb = rec.get("embedding")
                if not _id or emb is None:
                    # Embedding must be present to avoid recomputation
                    raise CommandError("Record missing required fields 'id' or 'embedding'")
                ids_batch.append(_id)
                docs_batch.append(doc)
                metas_batch.append(meta)
                embs_batch.append(emb)
                if len(ids_batch) >= batch_size:
                    flush_batch()
                    self.stdout.write(self.style.NOTICE(f"Imported {total} items…"))

        flush_batch()
        self.stdout.write(self.style.SUCCESS(f"Import complete: {total} items loaded into '{collection_name}'"))