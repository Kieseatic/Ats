from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from models.matching_logic import match_jobs
from api.resume_parsing import parse_pdf
from api.job_parsing import parse_job_description, parse_text_job_description
from api.interview_analysis import *
from api.rag_integration import *
from api import *

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://localhost:8080"])  # Allow SkillSphere to call this

# In-memory storage for job descriptions
all_job_descriptions = []

@app.route('/')
def index():
    return jsonify({
        "message": "ATS AI Analysis Service",
        "status": "running",
        "version": "2.0.0",
        "endpoints": {
            "legacy": [
                "POST /api/upload_job_description",
                "POST /api/upload_resume", 
                "POST /api/upload_interview",
                "POST /api/analyze"
            ],
            "new": [
                "POST /api/extract-resume-text",
                "POST /api/analyze-job",
                "POST /api/match-resume-job"
            ]
        }
    })

# Health check endpoint for SkillSphere to test connection
@app.route('/health')
def health_check():
    return jsonify({
        "service": "ATS AI Analysis Service",
        "status": "running",
        "version": "2.0.0"
    })

# ============= YOUR EXISTING ENDPOINTS (UNCHANGED) =============

@app.route('/api/upload_job_description', methods=['POST'])
def upload_job_desc():
    # Get the uploaded file
    file = request.files.get('job_description')
    if not file:
        return jsonify({"Error": "No job description uploaded"}), 400
    
    # Adding the file type in filename
    filename = file.filename
    # Operations for JSON files
    if filename.endswith('.json'):
        try:
            job_descriptions = json.load(file.stream)
            for job in job_descriptions:
                parsed_job = parse_job_description(job)
                all_job_descriptions.append(parsed_job)
        except Exception as e:
            return jsonify({"error": "Invalid JSON format"}), 400

    # Operations for txt files
    elif filename.endswith('.txt'):
        try:
            file_content = file.read().decode('utf-8')
            parsed_job = parse_text_job_description(file_content)
            all_job_descriptions.append(parsed_job)  # Adding the parsed txt lines to all job descriptions dictionary
        except Exception as e:
            return jsonify({"error": "Error reading text file"}), 400

    else:
        return jsonify({"error": "Unsupported file type, Please upload a txt or json file only"}), 400
    
    return jsonify({"message": "Job descriptions uploaded successfully", "job_descriptions": all_job_descriptions})

@app.route('/api/upload_resume', methods=['POST'])
def upload_resume():
    file = request.files.get('resume')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Parsing the PDF content now
    resume_text = parse_pdf(file)

    # Perform the matching logic with the extracted resume text
    job_matches = match_jobs(resume_text, all_job_descriptions)

    # Testing the response when the file is successfully parsed
    response = {
        'message': "Resume received",
        "filename": file.filename,
        "content preview": resume_text[:1000],  # Reduced preview size
        "matches": job_matches
    }
    return jsonify(response)

@app.route('/api/upload_interview', methods=['POST'])
def upload_interview():
    #retrieving the uploaded file 
    file = request.files.get('interview_video')

    if not file:
        return jsonify({"error": "No interview file uploaded"}), 400
    
    metadata = request.form.to_dict()
    if not metadata:
        return jsonify({"error": "Metadata is required"}), 400
    
    # Validate required metadata fields
    required_fields = ["interviewee", "position"]
    missing_fields = [field for field in required_fields if field not in metadata or not metadata[field].strip()]

    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    result = process_interview_video(file, metadata)

    return jsonify(result)

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Analyze the candidate's performance using RAG and OpenAI's summarization.
    """
    try:
        # Get query and job keywords from the request
        data = request.get_json()
        query = data.get("query", "")
        job_keywords = data.get("job_keywords", [])

        if not query:
            return jsonify({"error": "Query is required"}), 400
        if not isinstance(job_keywords, list):
            return jsonify({"error": "Job keywords should be a list"}), 400

        # Perform the analysis
        analysis_results = analyze_candidate_with_openai(query, job_keywords)

        return jsonify(analysis_results)
    except Exception as e:
        print(f"ERROR: Failed to analyze interview - {e}")
        return jsonify({"error": "Failed to analyze interview"}), 500

# ============= NEW ENDPOINTS FOR SKILLSPHERE INTEGRATION =============

@app.route('/api/extract-resume-text', methods=['POST'])
def extract_resume_text():
    """Extract text from uploaded resume for SkillSphere"""
    try:
        file = request.files.get('resume')
        if not file:
            return jsonify({"success": False, "error": "No resume file uploaded"}), 400
        
        # Extract text using existing parse_pdf function
        resume_text = parse_pdf(file)
        
        return jsonify({
            "success": True,
            "text": resume_text,
            "filename": file.filename,
            "length": len(resume_text)
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Text extraction failed: {str(e)}"}), 500

@app.route('/api/analyze-job', methods=['POST'])
def analyze_job():
    """Analyze job description and convert to structured format"""
    try:
        data = request.get_json()
        job_description = data.get('job_description', '')
        job_info = data.get('job_info', {})
        
        if not job_description:
            return jsonify({"success": False, "error": "Job description is required"}), 400
        
        # Use existing text parsing logic
        parsed_job = parse_text_job_description(job_description)
        
        # Add additional job info if provided
        if job_info:
            parsed_job.update(job_info)
        
        return jsonify({
            "success": True,
            "parsed_job": parsed_job
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Job analysis failed: {str(e)}"}), 500

@app.route('/api/match-resume-job', methods=['POST'])
def match_resume_job():
    """Match resume with job description and return percentage + analysis"""
    try:
        data = request.get_json()
        resume_text = data.get('resume_text', '')
        job_data = data.get('job_data', {})
        candidate_info = data.get('candidate_info', {})
        
        if not resume_text or not job_data:
            return jsonify({"success": False, "error": "Resume text and job data are required"}), 400
        
        # Use existing matching logic
        job_matches = match_jobs(resume_text, [job_data])
        
        if job_matches:
            match_result = job_matches[0]  # Get the first (and only) match
            
            return jsonify({
                "success": True,
                "match_percentage": round(match_result["score"], 2),
                "analysis": match_result["explanation"],
                "job_title": match_result["job_id"],
                "recommendation": get_recommendation(match_result["score"]),
                "candidate_info": candidate_info,
                "breakdown": {
                    "skills_score": match_result["explanation"].get("Skill Match", {}).get("score", 0),
                    "experience_score": match_result["explanation"].get("Experience Match", {}).get("score", 0),
                    "education_score": match_result["explanation"].get("Education Fit", {}).get("score", 0),
                    "contextual_score": match_result["explanation"].get("Contextual Similarity", {}).get("score", 0)
                }
            })
        else:
            return jsonify({"success": False, "error": "No matches found"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": f"Matching failed: {str(e)}"}), 500

def get_recommendation(score):
    """Get recommendation based on match score"""
    if score >= 80:
        return "Excellent match - Highly recommended"
    elif score >= 60:
        return "Good match - Consider for interview"
    elif score >= 40:
        return "Moderate match - Review carefully"
    else:
        return "Low match - May not be suitable"

if __name__ == '__main__':
    print("🚀 Starting ATS AI Analysis Service...")
    print("📋 Available endpoints:")
    print("   Legacy endpoints:")
    print("   - POST /api/upload_job_description")
    print("   - POST /api/upload_resume")
    print("   - POST /api/upload_interview")
    print("   - POST /api/analyze")
    print("   New endpoints:")
    print("   - POST /api/extract-resume-text")
    print("   - POST /api/analyze-job")
    print("   - POST /api/match-resume-job")
    print("🌐 Service running on http://localhost:5001")
    app.run(debug=True, port=5001)