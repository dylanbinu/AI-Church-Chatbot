import os
import sys
import json
import shutil
import warnings
import argparse

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import JSONLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

import config

def main():
    parser = argparse.ArgumentParser(description="Ingest Church Data")
    parser.add_argument("--church_id", type=str, default="heritage", help="Unique ID for the church (default: 'heritage')")
    parser.add_argument("--input_file", type=str, default="scraped_data.jsonl", help="Input JSONL file")
    parser.add_argument("--reset", action="store_true", help="Wipe the entire database before ingesting")
    
    args = parser.parse_args()

    print("="*50)
    print("   INGESTING KNOWLEDGE BASE")
    
    # Handle DB Reset
    if args.reset:
        if os.path.exists(config.CHROMA_PATH):
            try:
                shutil.rmtree(config.CHROMA_PATH)
                print(f"   [RESET] Cleared existing database at {config.CHROMA_PATH}")
            except PermissionError:
                print(f"[ERROR] Could not clear DB. Server might be running.", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"[ERROR] {e}", file=sys.stderr)
                sys.exit(1)
        os.makedirs(config.CHROMA_PATH, exist_ok=True)
    else:
        print(f"   [INFO] Appending to existing database at {config.CHROMA_PATH}")
        
    # --- LOAD MODEL ONCE (Optimization) ---
    print(f"   [INFO] Loading Embedding Model ({config.EMBEDDING_MODEL_NAME})...")
    embedding_model = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)

    # PRE-CLEANUP: If we are appending for a specific church, we must delete OLD data
    # Now we reuse the already loaded `embedding_model`
    if not args.reset and args.church_id:
        try:
            print(f"   [INFO] Removing old data for church_id: {args.church_id}")
            temp_db = Chroma(persist_directory=config.CHROMA_PATH, embedding_function=embedding_model)
            
            # Retrieve all docs to find IDs
            existing_docs = temp_db.get(where={"church_id": args.church_id})
            if existing_docs and existing_docs['ids']:
                ids_to_delete = existing_docs['ids']
                print(f"   [INFO] Deleting {len(ids_to_delete)} existing chunks for this church...")
                temp_db.delete(ids=ids_to_delete)
            else:
                print("   [INFO] No existing data found for this church.")
        except Exception as e:
            print(f"   [WARN] Could not clean up old data: {e}")

    # Determine Input File
    if os.path.isabs(args.input_file):
        data_path = args.input_file
    else:
        # Check current dir first, then project root fallback
        if os.path.exists(args.input_file):
            data_path = os.path.abspath(args.input_file)
        else:
            data_path = os.path.join(config.PROJECT_ROOT, args.input_file)

    if not os.path.exists(data_path):
        print(f"[ERROR] Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    # 1. Load Documents
    documents = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    # Support both formats (source/url)
                    src = data.get("source") or data.get("url")
                    if not src: continue

                    metadata = {"source": src}
                    if args.church_id:
                        metadata["church_id"] = args.church_id
                        
                    doc = Document(
                        page_content=data["content"] or data.get("text", ""),
                        metadata=metadata
                    )
                    documents.append(doc)
                except:
                    continue
    
    print(f"   Loaded {len(documents)} distinct pages from {args.input_file}.")

    # 2. Split Text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=300,
        separators=["\n\n", "\n", "###", "##", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"   Created {len(chunks)} searchable chunks.")

    # 3. Vectorize
    # Reuse the model loaded earlier
    BATCH_SIZE = 50
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]
        Chroma.from_documents(
            documents=batch,
            embedding=embedding_model,
            persist_directory=config.CHROMA_PATH
        )
        print(f"   Processed batch {i//BATCH_SIZE + 1}...")

    print("-" * 50)
    print("Ingestion Complete.")

if __name__ == "__main__":
    main()