import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# loading the sentence transformers model
model = SentenceTransformer('all-MiniLM-L6-v2')

embedding_dim = 384  # Dimension of embeddings for 'all-MiniLM-L6-v2'
index = faiss.IndexFlatIP(embedding_dim)  # FAISS index for cosine similarity
metadata_store = []  # To store metadata for each embedding


# Generate an embedding for the transcription and store it in a vector database
def store_in_vector_db(transcription, metadata):
    """
    Stores the transcription embedding and metadata in the FAISS index.

    Args:
        transcription (str): The transcription text.
        metadata (dict): Metadata for the transcription.

    Returns:
        int: The ID of the stored embedding.
    """
    global index, metadata_store

    # Debug: Print transcription and metadata
    print("Storing transcription (first 100 chars):", transcription[:100])  # Preview transcription
    print("Metadata:", metadata)

    # Step 1: Generate the embedding
    embedding = model.encode([transcription])  # Embedding shape should be (1, 384)

    # Debug: Print embedding shape
    print("Embedding shape:", embedding.shape)

    # Step 2: Normalize the embedding for cosine similarity
    faiss.normalize_L2(embedding)  # Normalizing embeddings
    print("Embedding normalized.")

    # Step 3: Add the embedding to the FAISS index
    index.add(embedding)
    print(f"FAISS index size after addition: {index.ntotal}")

    # Step 4: Store metadata
    metadata["transcription"] = transcription  # Ensure transcription is part of metadata
    metadata_store.append(metadata)
    print(f"Metadata store size after addition: {len(metadata_store)}")

    # Giving out the last element of the list, as any new data will be appended to the end of the list
    return len(metadata_store) - 1


def query_vector_db(query, top_k=5):
    """
    Quering the vector data to find the similar transcriptions.
    
    top_k is 5, so it will return 5 top results.

    It will return a list of top 5 results that are matching the metadata and similarity score.
    """
    global index, metadata_store  # they are set to global as they hold all the embeddings and metadata

    # Debug: Print the query
    print("Query text:", query)

    # Step 1: Generate the embedding for the query
    query_embedding = model.encode([query])  # This will convert the query text into embedding using the sentence transformer model

    # Debug: Print query embedding shape
    print("Query embedding shape:", query_embedding.shape)

    # Step 2: Normalize the embedding
    faiss.normalize_L2(query_embedding)  # Normalizing embeddings
    print("Query embedding normalized.")

    # Debug: Check FAISS index size before querying
    print(f"FAISS index size at query time: {index.ntotal}")

    # If the index is empty, return an empty result
    if index.ntotal == 0:
        print("Error: FAISS index is empty. No embeddings stored.")
        return []

    # Step 3: Perform the search
    distances, indices = index.search(query_embedding, top_k)  # This will search the FAISS index for similar matches

    # Debug: Print raw search results
    print("FAISS search distances:", distances)
    print("FAISS search indices:", indices)

    # Step 4: Retrieve metadata and similarity scores
    results = []  # To store the final results
    for i, idx in enumerate(indices[0]):
        if idx >= 0 and idx < len(metadata_store):  # Ensure the index is valid
            # Debug: Log valid match
            print(f"DEBUG: Match found - Index: {idx}, Similarity: {distances[0][i]}")

            # Include transcription in the result if available
            result = {
                "metadata": metadata_store[idx],
                "similarity": float(distances[0][i]),
                "transcription": metadata_store[idx].get("transcription", "")
            }
            results.append(result)
        else:
            # Debug: Log warning for invalid index
            print(f"WARNING: Invalid index {idx}. Metadata store size: {len(metadata_store)}")

    # Debug: Print final query results
    print("Query results:", results)

    return results
