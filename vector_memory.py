"""
Vector Memory Module for Azure BI Dashboard
Stores question-answer pairs as embeddings in SQL Server for semantic search.

How it works:
  1. User asks a question
  2. When they give thumbs up, we generate an embedding and save it
  3. Next time someone asks a similar question, we find cached answers

SQL analogy:
  - Old way: SELECT * FROM cache WHERE question = 'exact match' → no fuzzy matching
  - New way: SELECT * FROM cache WHERE embedding SIMILAR TO new_question (65% match) → fuzzy matching!
"""

import json
import pyodbc
from google import genai

def get_sql_connection(sql_server, sql_user, sql_password, database="HealthcareClaims"):
    """
    Create a connection to SQL Server for vector operations.

    Args:
        sql_server: Server name (e.g., "myserver.database.windows.net")
        sql_user: Username
        sql_password: Password
        database: Database name

    Returns:
        pyodbc connection object
    """
    drivers = pyodbc.drivers()
    sql_drivers = [d for d in drivers if 'SQL Server' in d]
    odbc_drivers = [d for d in sql_drivers if 'ODBC Driver' in d]
    driver_name = odbc_drivers[-1] if odbc_drivers else (sql_drivers[-1] if sql_drivers else 'SQL Server')

    conn_str = f"DRIVER={{{driver_name}}};SERVER={sql_server};DATABASE={database};UID={sql_user};PWD={sql_password};Timeout=15;"
    if driver_name != 'SQL Server':
        conn_str += "TrustServerCertificate=yes;"

    return pyodbc.connect(conn_str)


def save_vector_memory(gemini_client, sql_server, sql_user, sql_password,
                       user_question, sql_code, domain, agent_model, is_positive):
    """
    Save a question-answer pair as a vector embedding in SQL Server.
    Only saves if user gave thumbs UP (is_positive=True).

    Args:
        gemini_client: Google Gemini API client
        sql_server: SQL Server connection details
        sql_user: SQL Server username
        sql_password: SQL Server password
        user_question: The user's original question
        sql_code: The SQL that was generated
        domain: Which database this query used (HR, CLAIMS, etc.)
        agent_model: Which AI model generated the SQL (claude, gemini, etc.)
        is_positive: True if user gave thumbs up, False if thumbs down

    Returns:
        True if saved successfully, False otherwise
    """

    # Only save positive feedback
    if not is_positive:
        print("⏭️ Skipping vector save — user gave thumbs down")
        return False

    if not gemini_client:
        print("⚠️ GEMINI_API_KEY not configured — cannot save vector memory")
        return False

    try:
        # Step 1: Generate embedding from the question
        print(f"🔄 Generating embedding for: {user_question[:50]}...")
        embedding_response = gemini_client.models.embed_content(
            model="models/embedding-001",  # ✅ CORRECT model name
            content=user_question
        )

        vector_data = embedding_response.embedding
        vector_string = json.dumps(vector_data)

        # Step 2: Insert into SQL Server
        conn = get_sql_connection(sql_server, sql_user, sql_password)
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO ai_query_cache
                (user_question, sql_code, question_embedding, created_at)
            VALUES (?, ?, CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(768)), GETDATE())
        """

        cursor.execute(insert_query, user_question, sql_code, vector_string)
        conn.commit()
        conn.close()

        print(f"✅ Vector memory saved: '{user_question[:40]}...'")
        return True

    except Exception as e:
        print(f"[EMBED ERROR] Failed to save vector memory: {str(e)}")
        return False


def check_vector_memory(gemini_client, sql_server, sql_user, sql_password,
                        user_question, threshold=65.0):
    """
    Search SQL Server for similar past questions using vector distance.
    Returns the cached SQL if a similar question is found (>=threshold% match).

    This is like a "smart cache" — if someone asks a similar question,
    we can give them a hint based on what we learned before.

    Args:
        gemini_client: Google Gemini API client
        sql_server: SQL Server connection details
        sql_user: SQL Server username
        sql_password: SQL Server password
        user_question: The question to search for
        threshold: Minimum similarity score (0-100) to return a match

    Returns:
        Tuple: (cached_sql_code, similarity_score) or (None, 0) if no match
    """

    if not gemini_client:
        return None, 0

    try:
        # Step 1: Generate embedding for the search question
        embedding_response = gemini_client.models.embed_content(
            model="models/embedding-001",
            content=user_question
        )
        vector_data = embedding_response.embedding
        vector_string = json.dumps(vector_data)

        # Step 2: Search SQL Server using VECTOR_DISTANCE
        conn = get_sql_connection(sql_server, sql_user, sql_password)
        cursor = conn.cursor()

        # SQL Server 2024+ VECTOR_DISTANCE syntax
        # Returns the TOP 1 most similar question
        search_query = """
            SELECT TOP 1
                user_question,
                sql_code,
                (1 - VECTOR_DISTANCE('cosine', question_embedding,
                    CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(768)))) * 100 AS similarity_score
            FROM ai_query_cache
            ORDER BY similarity_score DESC
        """

        cursor.execute(search_query, vector_string)
        result = cursor.fetchone()
        conn.close()

        # Step 3: Return result if it meets the threshold
        if result:
            cached_question, cached_sql, similarity = result[0], result[1], result[2]
            if similarity >= threshold:
                print(f"💡 Found cached answer: {cached_question[:50]}... ({similarity:.1f}% match)")
                return cached_sql, similarity

        return None, 0

    except Exception as e:
        print(f"[VECTOR SEARCH] Error searching vector memory: {str(e)}")
        return None, 0


def get_vector_memory_stats(sql_server, sql_user, sql_password):
    """
    Get statistics about what's stored in vector memory.
    Useful for monitoring and debugging.

    Returns:
        Dict with count of cached questions, domains covered, etc.
    """
    try:
        conn = get_sql_connection(sql_server, sql_user, sql_password)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM ai_query_cache")
        total_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT CAST(JSON_VALUE(question_embedding, '$[0]') AS INT))
            FROM ai_query_cache
        """)

        conn.close()

        return {
            "total_cached_questions": total_count,
            "storage_size_mb": "N/A"  # You can enhance this later
        }
    except Exception as e:
        print(f"Error getting vector stats: {e}")
        return {"total_cached_questions": 0}
