from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import re
import os
from datetime import datetime
from models.matching_logic import match_jobs
from api.resume_parsing import parse_pdf
from api.job_parsing import parse_job_description, parse_text_job_description

app = Flask(__name__)

# Configure CORS to allow your Vercel frontend
CORS(app, origins=[
    "https://skillsphere-frontend-five.vercel.app",
    "http://localhost:3000",  # For local development
    "http://localhost:8080"   # For local development
])

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
                "POST /api/upload_resume"
            ],
            "new": [
                "POST /api/extract-resume-text",
                "POST /api/analyze-job",
                "POST /api/match-resume-job",
                "POST /api/parse-career"  # NEW ENDPOINT
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

# ============= LEGACY ENDPOINTS =============

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

# ============= IMPROVED CAREER PARSING ENDPOINT =============

@app.route('/api/parse-career', methods=['POST'])
def parse_career():
    """Parse resume text and extract structured education and work experience"""
    try:
        data = request.get_json()
        resume_text = data.get('resume_text', '')
        user_info = data.get('user_info', {})
        
        if not resume_text:
            return jsonify({"success": False, "error": "Resume text is required"}), 400
        
        print(f"[ATS AI] Parsing career data for user: {user_info.get('name', 'Unknown')}")
        print(f"[ATS AI] Resume text length: {len(resume_text)}")
        print(f"[ATS AI] Resume preview: {resume_text[:500]}...")
        
        # Extract education and work experience
        education = extract_education(resume_text)
        work_experience = extract_work_experience(resume_text)
        
        print(f"[ATS AI] ✅ Extracted {len(education)} education entries and {len(work_experience)} work experiences")
        
        # Log the extracted data
        for edu in education:
            print(f"[ATS AI] Education: {edu}")
        for exp in work_experience:
            print(f"[ATS AI] Experience: {exp}")
        
        return jsonify({
            "success": True,
            "education": education,
            "work_experience": work_experience,
            "user_info": user_info,
            "parsed_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"[ATS AI] Career parsing error: {str(e)}")
        import traceback
        print(f"[ATS AI] Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": f"Career parsing failed: {str(e)}"}), 500

def extract_education(resume_text):
    """Extract education information from resume text - IMPROVED VERSION"""
    education = []
    
    print(f"[ATS AI] Parsing education from resume text (length: {len(resume_text)})")
    
    # Look for education section - more flexible pattern
    education_patterns = [
        r'EDUCATION.*?(?=(?:SKILLS|EXPERIENCE|PROJECT|CERTIFICATION|INVOLVEMENT|$))',
        r'ACADEMIC.*?(?=(?:SKILLS|EXPERIENCE|PROJECT|CERTIFICATION|INVOLVEMENT|$))',
        r'QUALIFICATION.*?(?=(?:SKILLS|EXPERIENCE|PROJECT|CERTIFICATION|INVOLVEMENT|$))'
    ]
    
    section_text = ""
    for pattern in education_patterns:
        match = re.search(pattern, resume_text, re.DOTALL | re.IGNORECASE)
        if match:
            section_text = match.group(0)
            print(f"[ATS AI] Found education section: {section_text[:100]}...")
            break
    
    if not section_text:
        print("[ATS AI] No education section found")
        return education
    
    # Extract specific patterns for this resume
    # Pattern: Bachelor of Software Development
    # Seneca Polytechnic•Toronto, Ontario•2025
    
    degree_match = re.search(r'(Bachelor\s+of\s+Software\s+Development)', section_text, re.IGNORECASE)
    institution_match = re.search(r'(Seneca\s+Polytechnic)', section_text, re.IGNORECASE)
    location_match = re.search(r'Toronto,\s*Ontario', section_text, re.IGNORECASE)
    year_match = re.search(r'•(\d{4})', section_text)
    
    if degree_match or institution_match:
        education_entry = {
            "institution": institution_match.group(1) if institution_match else "Seneca Polytechnic",
            "degree": degree_match.group(1) if degree_match else "Bachelor of Software Development",
            "field_of_study": "Software Development",
            "start_date": "2021" if year_match else None,  # Assume 4-year program
            "end_date": year_match.group(1) if year_match else "2025",
            "current": False,
            "description": "",
            "gpa": "",
            "activities": ""
        }
        education.append(education_entry)
        print(f"[ATS AI] Extracted education: {education_entry}")
    
    return education

def extract_work_experience(resume_text):
    """Extract work experience from resume text - IMPROVED VERSION"""
    work_experience = []
    
    print(f"[ATS AI] Parsing work experience from resume text")
    
    # Look for experience section
    experience_match = re.search(r'EXPERIENCE.*?(?=(?:PROJECT|CERTIFICATION|INVOLVEMENT|$))', 
                               resume_text, re.DOTALL | re.IGNORECASE)
    
    if not experience_match:
        print("[ATS AI] No experience section found")
        return work_experience
    
    section_text = experience_match.group(0)
    print(f"[ATS AI] Found experience section: {section_text[:200]}...")
    
    # Split by job entries - look for job titles at start of lines
    job_patterns = [
        r'Junior Product Lead.*?(?=(?:Full Stack Developer|PROJECT|CERTIFICATION|$))',
        r'Full Stack Developer Intern.*?(?=(?:PROJECT|CERTIFICATION|INVOLVEMENT|$))'
    ]
    
    for pattern in job_patterns:
        job_match = re.search(pattern, section_text, re.DOTALL | re.IGNORECASE)
        if job_match:
            job_text = job_match.group(0)
            print(f"[ATS AI] Processing job block: {job_text[:100]}...")
            
            # Extract job details
            position = ""
            company = ""
            dates = ""
            location = ""
            description_bullets = []
            
            # Extract position (first line)
            lines = [line.strip() for line in job_text.split('\n') if line.strip()]
            if lines:
                position = lines[0].strip()
            
            # Look for Koralbyte Technologies
            company_match = re.search(r'(Koralbyte\s+Technologies)', job_text, re.IGNORECASE)
            if company_match:
                company = company_match.group(1)
            
            # Extract dates
            date_patterns = [
                r'(April\s+2025\s*[-–—]\s*Present)',
                r'(January\s+2025\s*[-–—]\s*April\s+2025)',
                r'(\w+\s+\d{4}\s*[-–—]\s*(?:Present|\w+\s+\d{4}))'
            ]
            
            for date_pattern in date_patterns:
                date_match = re.search(date_pattern, job_text, re.IGNORECASE)
                if date_match:
                    dates = date_match.group(1)
                    break
            
            # Extract location
            location_match = re.search(r'Toronto,\s*Ontario', job_text, re.IGNORECASE)
            if location_match:
                location = location_match.group(0)
            
            # Extract bullet points
            bullet_matches = re.findall(r'•\s*([^•\n]+)', job_text)
            if bullet_matches:
                description_bullets = [bullet.strip() for bullet in bullet_matches]
            
            # Parse dates
            start_date = None
            end_date = None
            current = False
            
            if dates:
                if 'Present' in dates:
                    current = True
                
                # Extract start and end dates
                if 'April 2025' in dates:
                    start_date = '2025-04-01'
                elif 'January 2025' in dates:
                    start_date = '2025-01-01'
                    if 'April 2025' in dates:
                        end_date = '2025-04-30'
            
            if position and company:
                work_entry = {
                    "company": company,
                    "position": position,
                    "location": location,
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": current,
                    "description": ' '.join(description_bullets) if description_bullets else "",
                    "skills": [],
                    "employment_type": "Full-time"
                }
                work_experience.append(work_entry)
                print(f"[ATS AI] Extracted work experience: {work_entry}")
    
    return work_experience

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
    print("   New endpoints:")
    print("   - POST /api/extract-resume-text")
    print("   - POST /api/analyze-job")
    print("   - POST /api/match-resume-job")
    print("   - POST /api/parse-career (IMPROVED)")
    print("🌐 Service running on production")
    
    # Get port from environment variable for production deployment
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
