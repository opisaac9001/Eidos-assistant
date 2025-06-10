import chromadb
from sentence_transformers import SentenceTransformer
import os
import shutil # For cleaning up test directory

class KnowledgeBase:
    def __init__(self, persist_directory: str | None = None,
                 collection_name: str = "pathos_knowledge",
                 model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initializes the Knowledge Base.

        Args:
            persist_directory (str, optional): Directory to persist ChromaDB data.
                                               If None, an in-memory EphemeralClient is used.
                                               Defaults to None.
            collection_name (str, optional): Name of the collection in ChromaDB.
                                             Defaults to "pathos_knowledge".
            model_name (str, optional): Name of the sentence transformer model to use.
                                        Defaults to 'all-MiniLM-L6-v2'.
        """
        self.model_name = model_name
        self.collection_name = collection_name

        try:
            self.embedding_model = SentenceTransformer(model_name)
            print(f"KnowledgeBase: SentenceTransformer model '{model_name}' loaded successfully.")
        except Exception as e:
            print(f"KnowledgeBase Error: Failed to load SentenceTransformer model '{model_name}'. Error: {e}")
            raise # Re-raise exception as embedding model is critical

        self.persist_directory = persist_directory
        if self.persist_directory:
            # Ensure the path is absolute for PersistentClient
            self.resolved_persist_directory = os.path.abspath(self.persist_directory)
            os.makedirs(self.resolved_persist_directory, exist_ok=True)
            print(f"KnowledgeBase: Using PersistentClient with data stored in: {self.resolved_persist_directory}")
            self.client = chromadb.PersistentClient(path=self.resolved_persist_directory)
        else:
            print("KnowledgeBase: Using EphemeralClient (in-memory database).")
            self.client = chromadb.EphemeralClient()

        try:
            # If providing embeddings directly in add(), embedding_function is not strictly needed here.
            # ChromaDB's default embedding function will be used if embeddings are not provided in add(),
            # but we intend to provide them.
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            print(f"KnowledgeBase: Collection '{self.collection_name}' loaded/created successfully.")
        except Exception as e:
            print(f"KnowledgeBase Error: Failed to get or create collection '{self.collection_name}'. Error: {e}")
            raise

        print(f"KnowledgeBase initialized. Model: {self.model_name}. Collection: {self.collection_name}.")

    def _split_text_into_chunks(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
        """
        Splits text into chunks.
        A simple implementation: split by paragraphs, then further if paragraphs are too long.
        """
        if not text:
            return []

        # First, split by double newlines (paragraphs)
        paragraphs = text.split("\n\n")

        chunks = []
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            if len(paragraph) <= chunk_size:
                chunks.append(paragraph)
            else:
                # Paragraph is too long, split it further by character count with overlap
                start = 0
                while start < len(paragraph):
                    end = start + chunk_size
                    chunk = paragraph[start:end]
                    chunks.append(chunk)
                    if end >= len(paragraph):
                        break
                    start += (chunk_size - chunk_overlap) # Move start point for next chunk
                    if start >= len(paragraph): # Ensure we don't create empty chunks if overlap is large
                        break

        # Filter out any potential empty strings that might have resulted from splitting
        return [chunk for chunk in chunks if chunk.strip()]


    def add_document(self, document_content: str, document_id: str):
        """
        Adds a document to the knowledge base.

        Args:
            document_content (str): The raw text content of the document.
            document_id (str): A unique identifier for the document.
        """
        if not document_content or not document_content.strip():
            print(f"KnowledgeBase Warning: Document content for '{document_id}' is empty. Skipping.")
            return

        chunks = self._split_text_into_chunks(document_content)

        if not chunks:
            print(f"KnowledgeBase Warning: No text chunks generated for document '{document_id}'. Skipping.")
            return

        try:
            embeddings = self.embedding_model.encode(chunks).tolist()
        except Exception as e:
            print(f"KnowledgeBase Error: Failed to generate embeddings for document '{document_id}'. Error: {e}")
            return

        metadatas = [{"source": document_id, "chunk_num": i} for i in range(len(chunks))]
        ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]

        try:
            self.collection.add(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            print(f"KnowledgeBase: Document '{document_id}' added with {len(chunks)} chunks.")
        except Exception as e:
            # This can happen for various reasons, e.g., duplicate IDs if run multiple times with same content
            # Or issues with ChromaDB itself.
            print(f"KnowledgeBase Error: Failed to add document '{document_id}' to collection. Error: {e}")


    def query(self, query_text: str, n_results: int = 3) -> list[str] | None:
        """
        Queries the knowledge base.

        Args:
            query_text (str): The query text.
            n_results (int, optional): Number of results to return. Defaults to 3.

        Returns:
            list[str] | None: A list of matching document chunks, or None if an error occurs.
        """
        if not query_text or not query_text.strip():
            print("KnowledgeBase Warning: Query text is empty.")
            return [] # Return empty list for empty query

        try:
            query_embedding = self.embedding_model.encode(query_text).tolist()
        except Exception as e:
            print(f"KnowledgeBase Error: Failed to generate embedding for query '{query_text[:50]}...'. Error: {e}")
            return None

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )

            # results['documents'] is a list containing one list of documents (since we sent one query_embedding)
            if results and results.get('documents') and results['documents'][0]:
                return results['documents'][0]
            else:
                print(f"KnowledgeBase: No results found for query: '{query_text[:50]}...'")
                return [] # Return empty list if no documents found
        except Exception as e:
            print(f"KnowledgeBase Error: Failed to query collection for '{query_text[:50]}...'. Error: {e}")
            return None

    def delete_collection(self):
        """Deletes the collection from the database."""
        if self.collection:
            try:
                self.client.delete_collection(name=self.collection_name)
                print(f"KnowledgeBase: Collection '{self.collection_name}' deleted successfully.")
                self.collection = None
            except Exception as e:
                print(f"KnowledgeBase Error: Failed to delete collection '{self.collection_name}'. Error: {e}")

    def clear_all_data_and_shutdown_persistent_client(self):
        """
        Deletes the collection and, if using a persistent client, removes the persist_directory.
        This is a destructive operation intended for cleanup, especially after tests.
        """
        self.delete_collection() # Try to delete the collection first

        if self.persist_directory and os.path.exists(self.resolved_persist_directory):
            try:
                # ChromaDB's PersistentClient might keep file locks, making direct shutil.rmtree difficult
                # while the client object is still active.
                # For robust cleanup, one might need to ensure the client is properly shut down or reset.
                # chromadb.PersistentClient doesn't have an explicit close/shutdown method in older versions.
                # Resetting the client might release locks.
                self.client.reset() # Resets the database, deleting all data in the client.
                print(f"KnowledgeBase: PersistentClient reset. All data in '{self.resolved_persist_directory}' should be cleared.")

                # After reset, the directory might still exist but be empty, or Chroma may have deleted it.
                # If it still exists and we want to remove the directory itself:
                if os.path.exists(self.resolved_persist_directory):
                    shutil.rmtree(self.resolved_persist_directory)
                    print(f"KnowledgeBase: Persistence directory '{self.resolved_persist_directory}' removed.")
            except Exception as e:
                print(f"KnowledgeBase Warning: Could not fully remove persistence directory '{self.resolved_persist_directory}'. Error: {e}")
        elif self.persist_directory:
            print(f"KnowledgeBase: Persistence directory '{self.resolved_persist_directory}' not found for cleanup.")


if __name__ == '__main__':
    print("\n--- Testing KnowledgeBase ---")

    # Define a test directory (relative to where this script is, or an absolute path)
    # For testing, this script is in eidos_assistant/core/
    # So, ../data/test_kb would be eidos_assistant/data/test_kb
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    test_persist_dir = os.path.join(current_script_dir, "..", "data", "test_knowledge_base_data")
    test_collection_name = "test_collection"

    print(f"Test persistence directory will be: {test_persist_dir}")

    # Ensure the directory is clean before test
    if os.path.exists(test_persist_dir):
        print(f"Warning: Test directory {test_persist_dir} already exists. Removing it for a clean test.")
        shutil.rmtree(test_persist_dir)

    kb = None # Initialize kb to None
    try:
        # Test with persistence
        print("\n--- Test 1: Initialize with Persistence ---")
        kb = KnowledgeBase(persist_directory=test_persist_dir, collection_name=test_collection_name)

        sample_doc_id_1 = "sample_constitution_excerpt"
        sample_content_1 = (
            "We the People of the United States, in Order to form a more perfect Union,\n\n"
            "establish Justice, insure domestic Tranquility, provide for the common defence,\n\n"
            "promote the general Welfare, and secure the Blessings of Liberty to ourselves\n\n"
            "and our Posterity, do ordain and establish this Constitution for the United States of America."
            "\n\nArticle I: All legislative Powers herein granted shall be vested in a Congress of the United States, "
            "which shall consist of a Senate and House of Representatives."
        )
        kb.add_document(sample_content_1, sample_doc_id_1)

        sample_doc_id_2 = "sample_science_fact"
        sample_content_2 = (
            "The mitochondria is the powerhouse of the cell.\n\nIt generates most of the cell's supply\n\n"
            "of adenosine triphosphate (ATP), used as a source of chemical energy."
        )
        kb.add_document(sample_content_2, sample_doc_id_2)

        print("\n--- Test 2: Query relevant to Document 1 ---")
        query1 = "What is the purpose of the US Constitution?"
        results1 = kb.query(query1, n_results=2)
        print(f"Query: \"{query1}\"")
        if results1:
            for i, res_chunk in enumerate(results1):
                print(f"Result chunk {i+1}:\n{res_chunk}\n---")
        else:
            print("No results or error for query 1.")

        print("\n--- Test 3: Query relevant to Document 2 ---")
        query2 = "What is ATP?"
        results2 = kb.query(query2, n_results=1)
        print(f"Query: \"{query2}\"")
        if results2:
            for i, res_chunk in enumerate(results2):
                print(f"Result chunk {i+1}:\n{res_chunk}\n---")
        else:
            print("No results or error for query 2.")

        print("\n--- Test 4: Query irrelevant to any document ---")
        query3 = "What is the best recipe for apple pie?"
        results3 = kb.query(query3, n_results=1)
        print(f"Query: \"{query3}\"")
        if results3: # Should be empty list if no results, or low similarity docs
            for i, res_chunk in enumerate(results3):
                print(f"Result chunk {i+1} (unexpected):\n{res_chunk}\n---")
        elif results3 == []:
             print("Correctly returned no results for irrelevant query.")
        else: # None
            print("Error occurred for query 3.")

        print("\n--- Test 5: Querying an empty knowledge base (after creating a new one) ---")
        # Test with in-memory client
        kb_empty_in_memory = KnowledgeBase(collection_name="test_empty_collection_in_memory") # No persist_directory
        query_empty = "Anything here?"
        results_empty = kb_empty_in_memory.query(query_empty)
        print(f"Query: \"{query_empty}\" on empty in-memory KB")
        if results_empty == []:
            print("Correctly returned no results from empty KB.")
        else:
            print(f"Unexpected results from empty KB: {results_empty}")
        kb_empty_in_memory.delete_collection()


    except Exception as e:
        print(f"An error occurred during KnowledgeBase testing: {e}")
    finally:
        print("\n--- Test Cleanup ---")
        if kb and kb.persist_directory: # If kb was initialized and used persistence
            print(f"Attempting to clean up persistent data for collection '{kb.collection_name}' and directory '{kb.resolved_persist_directory}'...")
            # This will delete the collection and then attempt to remove the directory.
            kb.clear_all_data_and_shutdown_persistent_client()
        else:
            # Fallback cleanup for the directory if kb object wasn't fully formed but dir was created
            if os.path.exists(test_persist_dir):
                print(f"Fallback cleanup: Removing test directory {test_persist_dir} as kb object might not be fully initialized or was in-memory.")
                shutil.rmtree(test_persist_dir)
            else:
                print("No persistent directory to clean up for the main test KB, or it was already removed.")

        # Second check, just in case the kb.clear_all_data... didn't remove the top-level test_persist_dir itself
        if os.path.exists(test_persist_dir):
            print(f"Warning: Test directory {test_persist_dir} still exists after cleanup attempt. Manual removal might be needed.")
        else:
            print(f"Test directory {test_persist_dir} successfully cleaned up or was not created.")

    print("\nKnowledgeBase testing complete.")
