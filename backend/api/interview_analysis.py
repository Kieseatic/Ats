'''
Here we will firstly save the uploaded video temporarily 

'''
from api.transcription_utils import transcribe_audio
from models.vector_db_utils import *
import moviepy.editor as mp
import os

def process_interview_video(interview_file,metadata):

    #save the video temporarily
    temp_video_path = "temp_video.mp4"
    interview_file.save(temp_video_path)

    try: 
        audio_path= extract_audio(temp_video_path)
        print("Audio extracted successfully:", audio_path)

        transcription = transcribe_audio(audio_path)
        print("Transcription preview:", transcription[:100])


        metadata["transcription_length"] = len(transcription)  # Add length to metadata
        embedding_id = store_in_vector_db(transcription, metadata)
        print("Embedding ID:", embedding_id)


        return {
            "message": "Interview processed successfully",
            "embedding_id": embedding_id,
            "metadata": metadata,
            "transcription": transcription
        }
    except Exception as e:
        return {"error": f"Failed to process interview: {str(e)}"}
    finally:
        # Clean up the temporary video file
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        #clean up the temp audio file
        if os.path.exists("temp_audio.wav"):
            os.remove("temp_audio.wav")

def extract_audio(video_path):
    
    audio_path = "temp_audio.wav"

    try:
        # Use moviepy to extract audio
        video = mp.VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path)

        video.close() #explicitly closing the video file to release the resources

        return audio_path
    except Exception as e:
        raise RuntimeError(f"Error extracting audio: {str(e)}")
    
