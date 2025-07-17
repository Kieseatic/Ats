from models.vector_db_utils import * 
from transformers import pipeline
import openai
from dotenv import load_dotenv
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
print("Hi")
print(openai.api_key)

def retrieve_relevant_segments(query,top_k =5):
    """
    This function will retrieve relevant segments from the vector database based on a query

        query(str) -> question or topic 
        top -> nunmber of top matches 
    """
        
    results = query_vector_db(query, top_k=top_k)

    print("Retrieved Segments: ", results)

    return results


def generate_contextual_summary(relevant_segments):
    """
    This function will use OpenAI's API model to get the contextual summary based on relevant segments.
    """

    if not relevant_segments:
        print("DEBUG: No relevant segments found for the query.")
        return "No relevant segments found for the query."

    # Combine the relevant segments into a single text
    combined_text = " ".join([segment.get("transcription", "") for segment in relevant_segments])

    if not combined_text.strip():
        print("DEBUG: No transcription text available for summarization.")
        return "No transcriptions available for summarization."

    # Debug: Print the combined text length
    print(f"DEBUG: Combined text length: {len(combined_text)}")
    print(f"DEBUG: Combined text preview: {combined_text[:500]}")  # Preview first 500 characters

    # Define OpenAI's prompt
    prompt = f"""
    You are a professional interview analyzer. Summarize the following candidate's responses,
    focusing on communication style, engagement, and attentiveness. Be concise yet insightful.
    
    Candidate Responses:
    {combined_text}
    """

    try:
        # Calling OpenAI's API
        print("DEBUG: Sending request to OpenAI API...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant specializing in interview analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )

        # Debug: Print the raw response
        print("DEBUG: OpenAI API response:", response)

        # Extract and return the summary
        if "choices" in response and response["choices"]:
            summary = response["choices"][0]["message"]["content"]
            print("DEBUG: Extracted summary:", summary)
            return summary
        else:
            print("ERROR: Missing or empty 'choices' in OpenAI API response.")
            return "Error: Could not generate a summary. No choices returned by OpenAI API."

    except KeyError as e:
        print(f"ERROR: KeyError in OpenAI API response - {e}")
        print("DEBUG: OpenAI API response:", response)  # Log full response for debugging
        return "Error: KeyError while generating summary. Please check API response."

    except Exception as e:
        print(f"ERROR: Exception occurred during summary generation - {e}")
        return "Error: Unexpected error during summary generation."


def analyze_candidate_with_openai(query, job_keywords):
    """
    This function will perform the analysis on the candidate using RAG and OpenAI

    query -> The interview question can also be the queries
    job_keywords -> Specified skills in the job description 

    at the end it will return a informative analysis on candidate's performance 
    """

    # Retrieve relevant transcription segments
    relevant_segments = retrieve_relevant_segments(query)

    # Generate contextual summary
    contextual_summary = generate_contextual_summary(relevant_segments)

    # Extract keywords from the combined transcription
    combined_transcription = " ".join([segment["transcription"] for segment in relevant_segments])

    #checkingn if the keywords in the job descritpion matches with any keyword in the interview transcript
    matched_keywords = [keywords for keywords in job_keywords if keywords in combined_transcription]

    # Calculate keyword match percentage
    keyword_match_percentage = len(matched_keywords) / len(job_keywords) * 100 if job_keywords else 0

    # Return analysis
    return {
        "contextual_summary": contextual_summary,
        "keyword_match_percentage": keyword_match_percentage,
        "matched_keywords": matched_keywords,
    }