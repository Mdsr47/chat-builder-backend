import faiss
import numpy as np
import os
import pickle
from sentence_transformers import SentenceTransformer
from database import supabase_client

model = SentenceTransformer("all-MiniLM-L6-v2")

BASE_DIR = "vector_store"

# Cache: chatbot_id -> (index, documents)
_stores: dict = {}


def _get_paths(chatbot_id: int):
    folder = os.path.join(BASE_DIR, str(chatbot_id))
    return os.path.join(folder, "faiss.index"), os.path.join(folder, "docs.pkl")


def load_index():
    """No-op now — indexes are loaded lazily per chatbot."""
    os.makedirs(BASE_DIR, exist_ok=True)


def _load_store(chatbot_id: int):
    """Load (or initialize) the index + docs for a specific chatbot."""
    # 1. RAM (Memory) Check - Reply immediately if available
    if chatbot_id in _stores:
        return _stores[chatbot_id]

    index_file, doc_file = _get_paths(chatbot_id)

    # 2. Disk Check & 3. Supabase Fallback
    if not os.path.exists(index_file) or not os.path.exists(doc_file):
        if supabase_client:
            try:
                print(f"Downloading index for chatbot {chatbot_id} from Supabase...")
                os.makedirs(os.path.dirname(index_file), exist_ok=True)
                
                # Try downloading index
                try:
                    res_index = supabase_client.storage.from_("chatbot_indexes").download(f"{chatbot_id}/faiss.index")
                    with open(index_file, "wb") as f:
                        f.write(res_index)
                except Exception as e:
                    print(f"No index found in Supabase for {chatbot_id} or error: {e}")

                # Try downloading docs
                try:
                    res_doc = supabase_client.storage.from_("chatbot_indexes").download(f"{chatbot_id}/docs.pkl")
                    with open(doc_file, "wb") as f:
                        f.write(res_doc)
                except Exception as e:
                    print(f"No docs found in Supabase for {chatbot_id} or error: {e}")
                    
            except Exception as e:
                print(f"Error communicating with Supabase: {e}")

    # Load from local files into RAM
    if os.path.exists(index_file):
        index = faiss.read_index(index_file)
    else:
        index = None

    if os.path.exists(doc_file):
        with open(doc_file, "rb") as f:
            documents = pickle.load(f)
    else:
        documents = []

    _stores[chatbot_id] = (index, documents)
    return index, documents


def _save_store(chatbot_id: int):
    index, documents = _stores[chatbot_id]
    index_file, doc_file = _get_paths(chatbot_id)

    os.makedirs(os.path.dirname(index_file), exist_ok=True)

    if index is not None:
        faiss.write_index(index, index_file)

    with open(doc_file, "wb") as f:
        pickle.dump(documents, f)
        
    # Sync to Supabase
    if supabase_client:
        try:
            print(f"Syncing index for chatbot {chatbot_id} to Supabase...")
            supabase_client.storage.from_("chatbot_indexes").upload(
                file=index_file,
                path=f"{chatbot_id}/faiss.index",
                file_options={"content-type": "application/octet-stream", "upsert": "true"}
            )
            supabase_client.storage.from_("chatbot_indexes").upload(
                file=doc_file,
                path=f"{chatbot_id}/docs.pkl",
                file_options={"content-type": "application/octet-stream", "upsert": "true"}
            )
        except Exception as e:
            print(f"Error syncing to Supabase: {e}")


def add_documents(chunks: list[str], source: str, chatbot_id: int):
    if not chunks:
        raise ValueError("No text chunks available to index.")

    index, documents = _load_store(chatbot_id)

    embeddings = model.encode(chunks)
    embeddings = np.array(embeddings).astype("float32")

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    if embeddings.size == 0 or embeddings.shape[0] == 0:
        raise ValueError("Embedding generation returned no vectors.")

    if index is None:
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)

    index.add(embeddings)

    for chunk in chunks:
        documents.append({"text": chunk, "source": source})

    _stores[chatbot_id] = (index, documents)
    _save_store(chatbot_id)


def search(query: str, chatbot_id: int, k: int = 5) -> list[dict]:
    index, documents = _load_store(chatbot_id)

    if index is None or len(documents) == 0:
        return []

    query_vec = model.encode([query])
    query_vec = np.array(query_vec).astype("float32")

    distances, indices = index.search(query_vec, min(k, len(documents)))

    results = []
    for i in indices[0]:
        if 0 <= i < len(documents):
            results.append(documents[i])

    return results


def delete_store(chatbot_id: int):
    """Call this when a chatbot is deleted."""
    index_file, doc_file = _get_paths(chatbot_id)

    if os.path.exists(index_file):
        os.remove(index_file)
    if os.path.exists(doc_file):
        os.remove(doc_file)
    if chatbot_id in _stores:
        del _stores[chatbot_id]
        
    if supabase_client:
        try:
            print(f"Deleting index for chatbot {chatbot_id} from Supabase...")
            supabase_client.storage.from_("chatbot_indexes").remove([f"{chatbot_id}/faiss.index", f"{chatbot_id}/docs.pkl"])
        except Exception as e:
            print(f"Error deleting from Supabase: {e}")


# import faiss
# import numpy as np
# import os
# import pickle
# from sentence_transformers import SentenceTransformer

# model = SentenceTransformer("all-MiniLM-L6-v2")

# INDEX_FILE = "vector_store/faiss.index"
# DOC_FILE = "vector_store/docs.pkl"

# index = None
# documents = []


# def load_index():
#     global index, documents

#     if os.path.exists(INDEX_FILE):
#         index = faiss.read_index(INDEX_FILE)
#     else:
#         index = None

#     if os.path.exists(DOC_FILE):
#         with open(DOC_FILE, "rb") as f:
#             documents = pickle.load(f)
#     else:
#         documents = []


# def save_index():
#     global index, documents

#     os.makedirs("vector_store", exist_ok=True)

#     if index:
#         faiss.write_index(index, INDEX_FILE)

#     with open(DOC_FILE, "wb") as f:
#         pickle.dump(documents, f)


# def add_documents(chunks, source, chatbot_id):
#     global index, documents

#     embeddings = model.encode(chunks)
#     embeddings = np.array(embeddings).astype("float32")

#     if index is None:
#         dim = embeddings.shape[1]
#         index = faiss.IndexFlatL2(dim)

#     index.add(embeddings)

#     for chunk in chunks:
#         documents.append({
#             "text": chunk,
#             "source": source,
#             "chatbot_id": chatbot_id
#         })

#     save_index()


# def search(query, chatbot_id=None, k=5):
#     global index, documents

#     if index is None:
#         return []

#     query_vec = model.encode([query])
#     query_vec = np.array(query_vec).astype("float32")

#     distances, indices = index.search(query_vec, k * 5)

#     results = []
#     for i in indices[0]:
#         if i < len(documents):
#             doc = documents[i]

#             # ✅ FIX: handle old docs that don't have chatbot_id key
#             doc_chatbot_id = doc.get("chatbot_id")  # returns None if key missing

#             if chatbot_id is None or doc_chatbot_id == chatbot_id:
#                 results.append(doc)

#     return results[:k]