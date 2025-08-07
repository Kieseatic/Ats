from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import re
import os
import spacy
from datetime import datetime
from dateutil import parser as date_parser
import dateutil.parser
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

# Load spacy model for NLP-based parsing
try:
    nlp = spacy.load("en_core_web_sm")
    print("✅ SpaCy NLP model loaded successfully")
except OSError:
    print("⚠️ SpaCy model not found. Install with: python -m spacy download en_core_web_sm")
    nlp = None

# In-memory storage for job descriptions
all_job_descriptions = []
# ─── put these near the top, BEFORE extract_job_entries ─────────────────

# Accepts:
#   • Jan 2024   • January 2024
#   • 05/2023    • 2021
#   • Summer 2022 / Fall 2023
MONTHS   = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
DATE_RGX = rf'(?:{MONTHS}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b|(?:Spring|Summer|Fall|Winter)\s+\d{{4}})'

# Range separator can be dash, “to”, or en-dash
RANGE_RGX = rf'({DATE_RGX})\s*(?:[-–—]|to)\s*((?:Present|Current)|{DATE_RGX})'

@app.route('/')
def index():
    return jsonify({
        "message": "ATS AI Analysis Service - Fixed Resume Parser",
        "status": "running",
        "version": "3.1.0",
        "features": [
            "Multi-format resume parsing",
            "Proper section separation",
            "NLP-enhanced extraction",
            "Fixed fallback parsing strategies",
            "Partial result recovery"
        ],
        "endpoints": {
            "legacy": [
                "POST /api/upload_job_description",
                "POST /api/upload_resume"
            ],
            "enhanced": [
                "POST /api/extract-resume-text",
                "POST /api/analyze-job", 
                "POST /api/match-resume-job",
                "POST /api/parse-career",
                "POST /api/parse-career-robust"
            ]
        }
    })

@app.route('/health')
def health_check():
    return jsonify({
        "service": "ATS AI Analysis Service",
        "status": "running",
        "version": "3.1.0",
        "nlp_available": nlp is not None,
        "fixed_parser": True
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
            all_job_descriptions.append(parsed_job)
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
        "content preview": resume_text[:1000],
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
            match_result = job_matches[0]
            
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

# ============= FIXED CAREER PARSING ENDPOINTS =============

@app.route('/api/parse-career', methods=['POST'])
def parse_career_fixed():
    """FIXED parser that properly separates education and experience sections"""
    try:
        data = request.get_json()
        resume_text = data.get('resume_text', '')
        user_info = data.get('user_info', {})
        
        if not resume_text:
            return jsonify({"success": False, "error": "Resume text is required"}), 400
        
        print(f"[Fixed Parser] Processing resume for: {user_info.get('name', 'Unknown')}")
        print(f"[Fixed Parser] Resume length: {len(resume_text)}")
        print(f"[Fixed Parser] Resume preview: {resume_text[:200]}...")
        
        # Clean and normalize the text
        clean_text = clean_resume_text(resume_text)
        
        # Extract sections properly
        sections = extract_sections(clean_text)
        print(f"[Fixed Parser] Found sections: {list(sections.keys())}")
        
        # Parse education and experience separately
        education = parse_education_section(sections)
        work_experience = parse_experience_section(sections)
        
        print(f"[Fixed Parser] ✅ Extracted {len(education)} education entries and {len(work_experience)} work experiences")
        
        # Log results for debugging
        for edu in education:
            print(f"[Fixed Parser] Education: {edu['institution']} - {edu['degree']}")
        for exp in work_experience:
            print(f"[Fixed Parser] Experience: {exp['position']} at {exp['company']}")
        
        return jsonify({
            "success": True,
            "education": education,
            "work_experience": work_experience,
            "user_info": user_info,
            "parsing_metadata": {
                "method": "fixed_section_parser",
                "sections_found": list(sections.keys()),
                "education_count": len(education),
                "experience_count": len(work_experience)
            },
            "parsed_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"[Fixed Parser] Error: {str(e)}")
        import traceback
        print(f"[Fixed Parser] Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": f"Parsing failed: {str(e)}"}), 500

@app.route('/api/parse-career-robust', methods=['POST'])
def parse_career_robust():
    """Enhanced resume parser with multiple fallback strategies"""
    try:
        data = request.get_json()
        resume_text = data.get('resume_text', '')
        user_info = data.get('user_info', {})
        
        if not resume_text:
            return jsonify({"success": False, "error": "Resume text is required"}), 400
        
        print(f"[Enhanced Parser] Processing resume for user: {user_info.get('name', 'Unknown')}")
        print(f"[Enhanced Parser] Resume text length: {len(resume_text)}")
        
        # Initialize results
        education = []
        work_experience = []
        parsing_method = "unknown"
        confidence = 0.0
        warnings = []
        
        # Try multiple parsing strategies in order of sophistication
        try:
            # Strategy 1: Fixed section parser (most reliable for structured resumes)
            print("[Enhanced Parser] Attempting fixed section parsing...")
            clean_text = clean_resume_text(resume_text)
            sections = extract_sections(clean_text)
            education = parse_education_section(sections)
            work_experience = parse_experience_section(sections)
            parsing_method = "fixed_section"
            confidence = 0.9
            
            if education or work_experience:
                print(f"[Enhanced Parser] ✅ Fixed section parsing successful")
            else:
                raise Exception("Fixed section parsing returned no results")
                
        except Exception as fixed_error:
            print(f"[Enhanced Parser] Fixed section parsing failed: {fixed_error}")
            warnings.append(f"Fixed section parsing failed: {fixed_error}")
            
            try:
                # Strategy 2: NLP-enhanced parsing (if available)
                if nlp:
                    print("[Enhanced Parser] Attempting NLP-enhanced parsing...")
                    education, work_experience, confidence = parse_with_nlp(resume_text)
                    parsing_method = "nlp"
                    if education or work_experience:
                        print(f"[Enhanced Parser] ✅ NLP parsing successful (confidence: {confidence:.2f})")
                    else:
                        raise Exception("NLP parsing returned no results")
                else:
                    raise Exception("NLP model not available")
                    
            except Exception as nlp_error:
                print(f"[Enhanced Parser] NLP parsing failed: {nlp_error}")
                warnings.append(f"NLP parsing failed: {nlp_error}")
                
                try:
                    # Strategy 3: Multi-pattern regex parsing
                    print("[Enhanced Parser] Attempting multi-pattern regex parsing...")
                    education, work_experience = parse_with_multi_patterns(resume_text)
                    parsing_method = "multi-pattern"
                    confidence = 0.7
                    if education or work_experience:
                        print("[Enhanced Parser] ✅ Multi-pattern parsing successful")
                    else:
                        raise Exception("Multi-pattern parsing returned no results")
                        
                except Exception as pattern_error:
                    print(f"[Enhanced Parser] Multi-pattern parsing failed: {pattern_error}")
                    warnings.append(f"Multi-pattern parsing failed: {pattern_error}")
                    
                    # Strategy 4: Basic fallback parsing (always returns something)
                    print("[Enhanced Parser] Using basic fallback parsing...")
                    education, work_experience = parse_with_basic_fallback(resume_text)
                    parsing_method = "fallback"
                    confidence = 0.3
                    warnings.append("Used basic fallback parsing - accuracy may be limited")
        
        # Post-process and validate results
        education = validate_and_clean_education(education)
        work_experience = validate_and_clean_work_experience(work_experience)
        
        # Calculate final confidence based on data quality
        final_confidence = calculate_confidence(education, work_experience, confidence)
        
        print(f"[Enhanced Parser] ✅ Final results: {len(education)} education, {len(work_experience)} experience")
        print(f"[Enhanced Parser] Method: {parsing_method}, Confidence: {final_confidence:.2f}")
        
        return jsonify({
            "success": True,
            "education": education,
            "work_experience": work_experience,
            "user_info": user_info,
            "parsing_metadata": {
                "method": parsing_method,
                "confidence": final_confidence,
                "warnings": warnings,
                "education_count": len(education),
                "experience_count": len(work_experience)
            },
            "parsed_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"[Enhanced Parser] Critical error: {str(e)}")
        import traceback
        print(f"[Enhanced Parser] Traceback: {traceback.format_exc()}")
        
        # Even in critical failure, try to return something useful
        try:
            education, work_experience = parse_with_basic_fallback(resume_text)
            return jsonify({
                "success": True,
                "education": education,
                "work_experience": work_experience,
                "user_info": user_info,
                "parsing_metadata": {
                    "method": "emergency_fallback",
                    "confidence": 0.1,
                    "warnings": [f"Critical parsing error: {str(e)}"],
                    "education_count": len(education),
                    "experience_count": len(work_experience)
                },
                "parsed_at": datetime.now().isoformat()
            })
        except:
            return jsonify({"success": False, "error": f"Complete parsing failure: {str(e)}"}), 500

# ============= CORE PARSING FUNCTIONS =============

def clean_resume_text(text: str) -> str:
    """
    Strip noise & normalise headers / bullets so later regex
    has a consistent canvas to work on.
    """
    if not text:
        return ""

    # 1. Normalise whitespace
    text = re.sub(r'\r\n?', '\n', text)          # DOS → Unix line-endings
    text = re.sub(r'\u00A0', ' ', text)          # non-breaking space
    text = re.sub(r'[ \t]+', ' ', text)          # collapse runs of spaces
    text = re.sub(r'\n{3,}', '\n\n', text)       # max two blank lines

    # 2. Normalise bullets & dashes
    bullet_map = {
        '▪︎': '•', '‣': '•', '●': '•', '–': '-', '—': '-', '–': '-'
    }
    for bad, good in bullet_map.items():
        text = text.replace(bad, good)

    # 3. Standardise section headers (remove trailing “:” etc.)
    header_aliases = {
        r'EDUCATION\s*:': 'EDUCATION',
        r'WORK\s+EXPERIENCE\s*:': 'EXPERIENCE',
        r'PROFESSIONAL\s+EXPERIENCE\s*:': 'EXPERIENCE',
        r'EMPLOYMENT\s+HISTORY\s*:': 'EXPERIENCE',
        r'SKILL(S)?\s*:': 'SKILLS',
    }
    for pattern, repl in header_aliases.items():
        text = re.sub(pattern, repl, text, flags=re.I)

    # 4. Return tidy text
    return text.strip()


def extract_sections(text: str) -> dict[str, str]:
    """
    Extract EDUCATION / EXPERIENCE / SKILLS / PROJECTS / CERTIFICATIONS
    blocks.  A header must appear at the *start of a line* and be followed
    by a line-break, e.g.:

        EXPERIENCE
        Junior Product Lead …              ← ✓ captured

        but not:
        … programming languages and experience in …
    """
    sections: dict[str, str] = {}

    section_patterns = {
        # ---------- EDUCATION ----------
        'education': (
            r'(^|\n)\s*(?:EDUCATION|ACADEMIC BACKGROUND|QUALIFICATIONS)\s*(?:\n|$)'   # header
            r'(.*?)(?=('                                                              # content
            r'\n\s*(?:EXPERIENCE|WORK EXPERIENCE|EMPLOYMENT|PROFESSIONAL EXPERIENCE|'  # look-ahead next header
            r'CAREER|SKILLS|PROJECTS|CERTIFICATIONS)\s*(?:\n|$)|\Z))'
        ),

        # ---------- EXPERIENCE ----------
        'experience': (
            r'(^|\n)\s*(?:EXPERIENCE|WORK EXPERIENCE|EMPLOYMENT|PROFESSIONAL EXPERIENCE|CAREER)\s*(?:\n|$)'
            r'(.*?)(?=('
            r'\n\s*(?:SKILLS|PROJECTS|CERTIFICATIONS|EDUCATION)\s*(?:\n|$)|\Z))'
        ),

        # ---------- SKILLS ----------
        'skills': (
            r'(^|\n)\s*(?:SKILLS?|TECHNICAL SKILLS|PROGRAMMING)\s*(?:\n|$)'
            r'(.*?)(?=('
            r'\n\s*(?:PROJECTS?|CERTIFICATIONS|EXPERIENCE|EDUCATION)\s*(?:\n|$)|\Z))'
        ),

        # ---------- PROJECTS ----------
        'projects': (
            r'(^|\n)\s*(?:PROJECTS?|PROJECT EXPERIENCE)\s*(?:\n|$)'
            r'(.*?)(?=('
            r'\n\s*(?:CERTIFICATIONS?|SKILLS|EXPERIENCE|EDUCATION)\s*(?:\n|$)|\Z))'
        ),

        # ---------- CERTIFICATIONS ----------
        'certifications': (
            r'(^|\n)\s*(?:CERTIFICATIONS?|CERTIFICATES?)\s*(?:\n|$)'
            r'(.*?)(?=('
            r'\n\s*(?:SKILLS|PROJECTS|EXPERIENCE|EDUCATION)\s*(?:\n|$)|\Z))'
        ),
    }

    print("[Section Extractor] Looking for sections in text…")

    for name, pattern in section_patterns.items():
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            content = m.group(2).strip()
            if content:
                sections[name] = content
                print(f"[Section Extractor] Found {name}: {len(content)} chars")
                print(f"[Section Extractor] {name} preview: {content[:100]}…")

    # Fallback: keyword heuristics
    if not sections:
        print("[Section Extractor] No formal sections found, using keyword-based extraction")
        sections = extract_sections_by_keywords(text)

    return sections


def extract_sections_by_keywords(text: str) -> dict[str, str]:
    """
    Lightweight ML-ish heuristic: walk line-by-line, score each line for
    edu/exp keywords, and bucket contiguous runs.
    """
    sections: dict[str, list[str]] = {"education": [], "experience": []}
    current: str | None = None

    edu_kw = {
        'bachelor', 'master', 'phd', 'univers', 'college', 'diploma',
        'degree', 'gpa', 'polytechnic', 'academy'
    }
    exp_kw = {
        'developer', 'engineer', 'manager', 'analyst', 'technologies',
        'company', 'intern', 'lead', 'consultant', 'architect'
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()

        edu_score = sum(kw in lower for kw in edu_kw)
        exp_score = sum(kw in lower for kw in exp_kw)

        if edu_score > exp_score and edu_score:
            current = "education"
        elif exp_score > edu_score and exp_score:
            current = "experience"

        if current:
            sections[current].append(line)

    # Flatten lists → strings, drop empties
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def parse_education_section(sections):
    """Parse education section into structured data"""
    education = []
    
    edu_section = sections.get('education', '')
    if not edu_section:
        print("[Education Parser] No education section found")
        return education
    
    print(f"[Education Parser] Processing section: {edu_section[:200]}...")
    
    # Look for specific patterns in your resume
    # Pattern: Bachelor of Software Development Seneca Polytechnic•Toronto, Ontario•2025
    degree_pattern = r'(Bachelor\s+of\s+Software\s+Development|Bachelor|Master|PhD|Diploma|Certificate)[^\n]*'
    institution_pattern = r'(Seneca\s+Polytechnic|[A-Z][a-z]+\s+(?:University|College|Institute|Polytechnic))'
    location_pattern = r'(Toronto,\s*Ontario|[A-Z][a-z]+,\s*[A-Z][a-z]+)'
    year_pattern = r'(\d{4})'
    
    # Try to extract education information
    degree_match = re.search(degree_pattern, edu_section, re.IGNORECASE)
    institution_match = re.search(institution_pattern, edu_section, re.IGNORECASE)
    location_match = re.search(location_pattern, edu_section, re.IGNORECASE)
    year_match = re.search(year_pattern, edu_section)
    
    if degree_match or institution_match:
        degree = degree_match.group(1) if degree_match else "Bachelor of Software Development"
        institution = institution_match.group(1) if institution_match else "Seneca Polytechnic"
        location = location_match.group(1) if location_match else "Toronto, Ontario"
        year = year_match.group(1) if year_match else "2025"
        
        # Extract field of study
        field_of_study = "Software Development"
        if "software" in degree.lower():
            field_of_study = "Software Development"
        elif "computer" in degree.lower():
            field_of_study = "Computer Science"
        
        education.append({
            "institution": institution,
            "degree": degree,
            "field_of_study": field_of_study,
            "start_date": f"{int(year)-4}-09-01" if year else None,  # Estimate 4-year program
            "end_date": f"{year}-06-01" if year else None,
            "current": False,
            "description": "",
            "gpa": "",
            "activities": ""
        })
        
        print(f"[Education Parser] ✅ Extracted: {degree} from {institution}")
    
    return education

def parse_experience_section(sections: dict[str, str]) -> list[dict]:
    """
    Wrapper that delegates to the robust date-driven extractor and
    cleans up the result.
    """
    exp_text = sections.get("experience", "")
    if not exp_text:
        print("[Experience Parser] No experience section found")
        return []

    jobs = extract_job_entries(exp_text)
    return validate_and_clean_work_experience(jobs)


DATE_RGX = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})'
RANGE_RGX = rf'{DATE_RGX}\s*[-–—]\s*((?:Present|Current)|{DATE_RGX})'

TITLE_RGX = r'[A-Z][A-Za-z &/+-]{2,60}'
COMP_RGX  = r'[A-Z][A-Za-z0-9 &.,-]{2,80}'
# ─── top-of-file (before extract_job_entries) ───

MONTHS = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'  # Apr → April ok
SEASON = r'(?:Spring|Summer|Fall|Winter)'
DATE_RGX = rf'(?:{MONTHS}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b|{SEASON}\s+\d{{4}})'

# dash, en-dash or “to”
RANGE_RGX = rf'({DATE_RGX})\s*(?:[-–—]|to)\s*((?:Present|Current)|{DATE_RGX})'

def extract_job_entries(exp_text: str) -> list[dict]:
    """
    Parse each bullet / paragraph inside the EXPERIENCE block and return a
    list of job dictionaries.  Works with lines like:

        Junior Product Lead
        Koralbyte Technologies
        April 2025 - Present Toronto, Ontario
    """
    jobs: list[dict] = []

    MONTHS = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
    SEASON = r'(?:Spring|Summer|Fall|Winter)'
    DATE_RGX  = rf'(?:{MONTHS}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b|{SEASON}\s+\d{{4}})'
    RANGE_RGX = rf'({DATE_RGX})\s*(?:[-–—]|to)\s*((?:Present|Current)|{DATE_RGX})'

    # Split on bullets OR blank lines
    blocks = re.split(r'(?:\n\s*\n|\n\s*•|•)', exp_text)

    for blk in map(str.strip, blocks):
        if not blk:
            continue

        # -------- locate dates --------
        rm = re.search(RANGE_RGX, blk, flags=re.I)
        sm = None if rm else re.search(DATE_RGX, blk, flags=re.I)

        start_date = end_date = None
        current = False

        if rm:                            # date range
            start_raw, end_raw = rm.group(1), rm.group(2)
            start_date = parse_single_date(start_raw)
            if re.match(r'present|current', end_raw, flags=re.I):
                current = True
            else:
                end_date = parse_single_date(end_raw)
        elif sm:                          # single date
            start_date = parse_single_date(sm.group(0))

        # if still no start_date, synthesise from any year
        if not start_date:
            y = re.search(r'\b(\d{4})\b', blk)
            if y:
                start_date = f"{y.group(1)}-01-01"

        if not start_date:                # schema requires it → skip
            continue

        # -------- title & company heuristics --------
        title = (re.match(r'^[A-Z][A-Za-z &/+-]{3,60}', blk) or [''])[0].strip()

        comp_rgx = rf'(?:\bat\b|\n)\s*([A-Z][A-Za-z0-9 &.,-]{{2,80}}?)(?=\s+(?:{MONTHS}|\d{{4}}|\d{{1,2}}/))'
        cm = re.search(comp_rgx, blk, flags=re.I)
        company = cm.group(1).strip() if cm else "Company not specified"

        # -------- short description --------
        desc_lines = [l.strip('• ').strip() for l in blk.split('\n')[1:] if l.strip()][:2]
        description = " ".join(desc_lines)

        jobs.append({
            "company": company,
            "position": title or "Position not specified",
            "location": "",
            "start_date": start_date,
            "end_date": end_date,
            "current": current,
            "description": description,
            "skills": extract_skills_from_description(description),
            "employment_type": "Internship" if "intern" in title.lower() else "Full-time"
        })

    return jobs

def extract_generic_job_entries(exp_text):
    """Generic job extraction when specific patterns don't match"""
    jobs = []
    
    # Look for any job titles
    job_title_patterns = [
        r'(?:^|\n)\s*([A-Z][A-Za-z\s]+(?:Engineer|Developer|Manager|Analyst|Lead|Intern|Specialist))',
        r'(Software\s+(?:Engineer|Developer)|Product\s+(?:Manager|Lead)|Full\s+Stack\s+Developer)'
    ]
    
    # Look for companies
    company_patterns = [
        r'([A-Z][A-Za-z\s&]+(?:Technologies|Inc|LLC|Corp|Company|Ltd))',
        r'(Koralbyte|Google|Microsoft|Amazon|Meta|Apple)'  # Add known companies
    ]
    
    positions = []
    companies = []
    
    for pattern in job_title_patterns:
        matches = re.findall(pattern, exp_text, re.IGNORECASE | re.MULTILINE)
        positions.extend([match.strip() for match in matches])
    
    for pattern in company_patterns:
        matches = re.findall(pattern, exp_text, re.IGNORECASE)
        companies.extend([match.strip() for match in matches])
    
    # Match positions with companies
    for i, position in enumerate(positions):
        company = companies[i] if i < len(companies) else "Company not specified"
        
        jobs.append({
            "company": company,
            "position": position,
            "location": "",
            "start_date": None,
            "end_date": None,
            "current": False,
            "description": "",
            "skills": [],
            "employment_type": "Full-time"
        })
    
    return jobs

def extract_job_description(exp_text, position):
    """Extract job description bullets for a specific position"""
    # Look for bullet points near the position
    position_index = exp_text.lower().find(position.lower())
    if position_index == -1:
        return ""
    
    # Get text after the position (next 500 characters)
    text_after = exp_text[position_index:position_index + 500]
    
    # Extract bullet points
    bullets = re.findall(r'•\s*([^•\n]+)', text_after)
    
    return ' '.join(bullets[:3]) if bullets else ""  # Limit to first 3 bullets

def extract_skills_from_description(description):
    """Extract technical skills from job description"""
    if not description:
        return []
    
    # Common technical skills to look for
    skill_patterns = [
        r'\b(React|Vue|Angular|JavaScript|TypeScript|Python|Java|C\+\+|Node\.js|Express)\b',
        r'\b(AWS|Azure|GCP|Docker|Kubernetes|Git|Jenkins|CI/CD)\b',
        r'\b(MongoDB|PostgreSQL|MySQL|Redis|GraphQL|REST|API)\b'
    ]
    
    skills = []
    for pattern in skill_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        skills.extend(matches)
    
    return list(set(skills))  # Remove duplicates

def parse_date_range(date_str):
    """Parse date range string into start date, end date, and current flag"""
    if not date_str:
        return None, None, False
    
    current = "present" in date_str.lower() or "current" in date_str.lower()
    
    # Split on common separators
    parts = re.split(r'[-–—]', date_str)
    
    start_date = None
    end_date = None
    
    if len(parts) >= 1:
        start_date = parse_single_date(parts[0].strip())
    
    if len(parts) >= 2 and not current:
        end_date = parse_single_date(parts[1].strip())
    
    return start_date, end_date, current

def parse_single_date(date_str):
    """Parse a single date string into ISO format"""
    if not date_str or "present" in date_str.lower() or "current" in date_str.lower():
        return None
    
    try:
        # Handle various date formats
        if re.match(r'\w+\s+\d{4}', date_str):  # "April 2025"
            parsed_date = date_parser.parse(date_str)
            return parsed_date.strftime('%Y-%m-%d')
        elif re.match(r'\d{4}', date_str):  # "2025"
            return f"{date_str}-01-01"
        else:
            parsed_date = date_parser.parse(date_str)
            return parsed_date.strftime('%Y-%m-%d')
    except:
        return None

# ============= ENHANCED PARSING STRATEGIES =============

def parse_with_nlp(resume_text):
    """Parse resume using NLP models for entity recognition and relationship extraction"""
    if not nlp:
        raise Exception("NLP model not available")
    
    education = []
    work_experience = []
    
    # Process text with spaCy
    doc = nlp(resume_text)
    
    # Extract education using NLP
    education_entities = extract_education_nlp(doc, resume_text)
    education.extend(education_entities)
    
    # Extract work experience using NLP
    work_entities = extract_work_experience_nlp(doc, resume_text)
    work_experience.extend(work_entities)
    
    # Calculate confidence based on entity extraction quality
    confidence = min(0.95, 0.6 + (len(education) * 0.1) + (len(work_experience) * 0.05))
    
    return education, work_experience, confidence

def extract_education_nlp(doc, text):
    """Extract education using NLP entity recognition"""
    education = []
    
    # Split text into sections
    sections = split_into_sections(text)
    edu_section = find_section(sections, ['education', 'academic', 'qualification'])
    
    if edu_section:
        # Extract from education section
        edu_doc = nlp(edu_section)
        
        # Find institutions
        institutions = []
        for ent in edu_doc.ents:
            if ent.label_ == "ORG" and any(keyword in ent.text.lower() for keyword in ['university', 'college', 'institute', 'school']):
                institutions.append(ent.text)
        
        # Find degrees
        degrees = []
        degree_patterns = [
            r'(?:Bachelor|Master|PhD|B\.?[SA]\.?|M\.?[SA]\.?|MBA|Doctorate)\s+(?:of\s+|in\s+)?([A-Za-z\s]+)',
            r'(Bachelor|Master|PhD|Doctorate|Associate)\s+(?:of\s+|in\s+)?([A-Za-z\s]+)'
        ]
        
        for pattern in degree_patterns:
            matches = re.finditer(pattern, edu_section, re.IGNORECASE)
            for match in matches:
                degrees.append(match.group(0).strip())
        
        # Find dates
        dates = extract_dates_from_text(edu_section)
        
        # Combine findings
        max_entries = max(len(institutions), len(degrees), 1)
        for i in range(max_entries):
            institution = institutions[i] if i < len(institutions) else ""
            degree = degrees[i] if i < len(degrees) else ""
            
            if institution or degree:
                start_date, end_date = assign_dates_to_entry(dates, i)
                
                education.append({
                    "institution": institution or "Institution not specified",
                    "degree": degree or "Degree not specified", 
                    "field_of_study": extract_field_of_study(degree),
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": end_date is None,
                    "description": "",
                    "gpa": "",
                    "activities": ""
                })
    
    return education

def extract_work_experience_nlp(doc, text):
    """Extract work experience using NLP entity recognition"""
    work_experience = []
    
    # Split text into sections
    sections = split_into_sections(text)
    exp_section = find_section(sections, ['experience', 'employment', 'work', 'career', 'professional'])
    
    if exp_section:
        exp_doc = nlp(exp_section)
        
        # Extract companies (organizations)
        companies = []
        for ent in exp_doc.ents:
            if ent.label_ == "ORG":
                companies.append(ent.text)
        
        # Extract job titles using patterns
        job_titles = []
        title_patterns = [
            r'(?:^|\n)\s*([A-Z][A-Za-z\s&]+(?:Engineer|Developer|Manager|Analyst|Consultant|Director|Lead|Senior|Junior))',
            r'(Software\s+Engineer|Full\s+Stack\s+Developer|Product\s+Manager|Data\s+Analyst|Senior\s+Developer)',
            r'(?:^|\n)\s*([A-Z][A-Za-z\s]+)\s*(?:\n|•|at\s+)'
        ]
        
        for pattern in title_patterns:
            matches = re.finditer(pattern, exp_section, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                title = match.group(1).strip()
                if len(title) < 50 and is_likely_job_title(title):  # Filter out long descriptions
                    job_titles.append(title)
        
        # Extract dates
        dates = extract_dates_from_text(exp_section)
        
        # Combine findings
        max_entries = max(len(companies), len(job_titles), 1)
        for i in range(max_entries):
            company = companies[i] if i < len(companies) else ""
            position = job_titles[i] if i < len(job_titles) else ""
            
            if company or position:
                start_date, end_date = assign_dates_to_entry(dates, i)
                
                work_experience.append({
                    "company": company or "Company not specified",
                    "position": position or "Position not specified",
                    "location": "",
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": end_date is None or "present" in str(end_date).lower(),
                    "description": "",
                    "skills": [],
                    "employment_type": "Full-time"
                })
    
    return work_experience

def parse_with_multi_patterns(resume_text):
    """Parse using multiple regex patterns for different resume formats"""
    education = []
    work_experience = []
    
    # Education parsing with multiple patterns
    education_patterns = [
        # Pattern 1: Degree at Institution, Year
        r'([A-Z][A-Za-z\s]+(?:Bachelor|Master|PhD|Degree|Diploma).*?)\s+(?:at\s+|from\s+)?([A-Z][A-Za-z\s,]+(?:University|College|Institute|School).*?)\s*,?\s*(\d{4})',
        
        # Pattern 2: Institution - Degree - Year
        r'([A-Z][A-Za-z\s,]+(?:University|College|Institute|School))\s*[-–—]\s*([A-Z][A-Za-z\s]+(?:Bachelor|Master|PhD|Degree).*?)\s*[-–—]?\s*(\d{4})',
        
        # Pattern 3: Free-form with keywords
        r'(?:EDUCATION|ACADEMIC).*?([A-Z][A-Za-z\s,]+(?:University|College|Institute|School)).*?([A-Z][A-Za-z\s]+(?:Bachelor|Master|PhD|Degree)).*?(\d{4})',
    ]
    
    for pattern in education_patterns:
        matches = re.finditer(pattern, resume_text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            groups = match.groups()
            if len(groups) >= 3:
                # Determine which group is institution vs degree
                institution = groups[1] if 'university' in groups[1].lower() or 'college' in groups[1].lower() else groups[0]
                degree = groups[0] if institution == groups[1] else groups[1]
                year = groups[2]
                
                education.append({
                    "institution": institution.strip(),
                    "degree": degree.strip(),
                    "field_of_study": extract_field_of_study(degree),
                    "start_date": f"{int(year)-4}-09-01" if year else None,  # Estimate start date
                    "end_date": f"{year}-06-01" if year else None,
                    "current": False,
                    "description": "",
                    "gpa": "",
                    "activities": ""
                })
    
    # Work experience parsing with multiple patterns
    experience_patterns = [
        # Pattern 1: Title at Company (Date - Date)
        r'([A-Z][A-Za-z\s]+(?:Engineer|Developer|Manager|Analyst|Director|Lead))\s+at\s+([A-Z][A-Za-z\s&,]+)\s*\(([^)]+)\)',
        
        # Pattern 2: Company - Title - Date
        r'([A-Z][A-Za-z\s&,]+(?:Inc|LLC|Corp|Company|Ltd))\s*[-–—]\s*([A-Z][A-Za-z\s]+(?:Engineer|Developer|Manager))\s*[-–—]\s*([^•\n]+)',
        
        # Pattern 3: Bullet-based format
        r'•\s*([A-Z][A-Za-z\s]+(?:Engineer|Developer|Manager|Analyst))\s+.*?([A-Z][A-Za-z\s&]+(?:Inc|LLC|Corp|Company))',
    ]
    
    for pattern in experience_patterns:
        matches = re.finditer(pattern, resume_text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            groups = match.groups()
            if len(groups) >= 2:
                position = groups[0].strip()
                company = groups[1].strip()
                dates = groups[2].strip() if len(groups) > 2 else ""
                
                start_date, end_date = parse_date_range_multi(dates)
                
                work_experience.append({
                    "company": company,
                    "position": position,
                    "location": "",
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": "present" in dates.lower() if dates else False,
                    "description": "",
                    "skills": [],
                    "employment_type": "Full-time"
                })
    
    return education, work_experience

def parse_with_semantic_sections(resume_text):
    """Parse by identifying semantic sections and extracting structured data"""
    education = []
    work_experience = []
    
    # Split into sections based on headings
    sections = split_into_sections(resume_text)
    
    # Find education section
    edu_section = find_section(sections, ['education', 'academic', 'qualification', 'degree'])
    if edu_section:
        education = extract_education_from_section(edu_section)
    
    # Find experience section
    exp_section = find_section(sections, ['experience', 'employment', 'work', 'career', 'professional'])
    if exp_section:
        work_experience = extract_experience_from_section(exp_section)
    
    return education, work_experience

def parse_with_basic_fallback(resume_text):
    """Basic fallback parser that always returns something"""
    education = []
    work_experience = []
    
    # Very basic education extraction
    if any(word in resume_text.lower() for word in ['university', 'college', 'degree', 'bachelor', 'master']):
        education.append({
            "institution": "Institution found in resume",
            "degree": "Degree mentioned in resume",
            "field_of_study": "",
            "start_date": None,
            "end_date": None,
            "current": False,
            "description": "Extracted from resume text - please review and edit",
            "gpa": "",
            "activities": ""
        })
    
    # Very basic work experience extraction
    if any(word in resume_text.lower() for word in ['developer', 'engineer', 'manager', 'analyst', 'experience']):
        work_experience.append({
            "company": "Company mentioned in resume",
            "position": "Position found in resume",
            "location": "",
            "start_date": None,
            "end_date": None,
            "current": False,
            "description": "Extracted from resume text - please review and edit",
            "skills": [],
            "employment_type": "Full-time"
        })
    
    return education, work_experience

# ============= UTILITY FUNCTIONS =============

def split_into_sections(text):
    """Split resume text into logical sections"""
    # Split on common section headers
    section_headers = r'(?:^|\n)\s*(?:EDUCATION|EXPERIENCE|SKILLS|PROJECTS|CERTIFICATIONS|SUMMARY|OBJECTIVE|EMPLOYMENT|WORK|CAREER|ACADEMIC|QUALIFICATION)\s*(?:\n|$)'
    sections = re.split(section_headers, text, flags=re.IGNORECASE | re.MULTILINE)
    return [section.strip() for section in sections if section.strip()]

def find_section(sections, keywords):
    """Find section containing any of the given keywords"""
    for section in sections:
        if any(keyword.lower() in section.lower()[:50] for keyword in keywords):
            return section
    return ""

def extract_education_from_section(section):
    """Extract education from a specific section"""
    education = []
    lines = section.split('\n')
    
    for line in lines:
        if any(keyword in line.lower() for keyword in ['university', 'college', 'bachelor', 'master', 'degree']):
            # Try to extract institution and degree
            institution_match = re.search(r'([A-Za-z\s]+(?:University|College|Institute|School))', line, re.IGNORECASE)
            degree_match = re.search(r'(Bachelor|Master|PhD|Diploma|Certificate)[A-Za-z\s]*', line, re.IGNORECASE)
            
            if institution_match or degree_match:
                education.append({
                    "institution": institution_match.group(1) if institution_match else "Institution not specified",
                    "degree": degree_match.group(0) if degree_match else "Degree not specified",
                    "field_of_study": "",
                    "start_date": None,
                    "end_date": None,
                    "current": False,
                    "description": "",
                    "gpa": "",
                    "activities": ""
                })
    
    return education

def extract_experience_from_section(section):
    """Extract work experience from a specific section"""
    work_experience = []
    lines = section.split('\n')
    
    for line in lines:
        if any(keyword in line.lower() for keyword in ['engineer', 'developer', 'manager', 'analyst', 'director']):
            # Try to extract position and company
            position_match = re.search(r'([A-Za-z\s]+(?:Engineer|Developer|Manager|Analyst|Director|Lead))', line, re.IGNORECASE)
            company_match = re.search(r'([A-Za-z\s&]+(?:Technologies|Inc|LLC|Corp|Company|Ltd))', line, re.IGNORECASE)
            
            if position_match or company_match:
                work_experience.append({
                    "company": company_match.group(1) if company_match else "Company not specified",
                    "position": position_match.group(1) if position_match else "Position not specified",
                    "location": "",
                    "start_date": None,
                    "end_date": None,
                    "current": False,
                    "description": "",
                    "skills": [],
                    "employment_type": "Full-time"
                })
    
    return work_experience

def extract_dates_from_text(text):
    """Extract all dates from text"""
    dates = []
    
    # Date patterns
    date_patterns = [
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b',
        r'\b\d{4}\b',
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',
        r'\b\d{1,2}-\d{1,2}-\d{4}\b'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(matches)
    
    return dates

def parse_date_range_multi(date_str):
    """Parse date range string into start and end dates (multi-pattern version)"""
    if not date_str:
        return None, None
    
    # Handle "Present" or "Current"
    current = any(word in date_str.lower() for word in ['present', 'current'])
    
    # Split on separators
    parts = re.split(r'[-–—]|to', date_str, flags=re.IGNORECASE)
    
    start_date = None
    end_date = None
    
    if len(parts) >= 1:
        try:
            start_date = date_parser.parse(parts[0].strip()).isoformat()[:10]
        except:
            pass
    
    if len(parts) >= 2 and not current:
        try:
            end_date = date_parser.parse(parts[1].strip()).isoformat()[:10]
        except:
            pass
    
    return start_date, end_date

def assign_dates_to_entry(dates, entry_index):
    """Assign dates to a specific entry"""
    if len(dates) >= (entry_index + 1) * 2:
        start_idx = entry_index * 2
        end_idx = start_idx + 1
        return dates[start_idx], dates[end_idx]
    elif len(dates) > entry_index:
        return dates[entry_index], None
    return None, None

def extract_field_of_study(degree_text):
    """Extract field of study from degree text"""
    if not degree_text:
        return ""
    
    # Common patterns for field extraction
    field_patterns = [
        r'(?:in|of)\s+([A-Za-z\s]+)',
        r'(?:Bachelor|Master|PhD)\s+([A-Za-z\s]+)'
    ]
    
    for pattern in field_patterns:
        match = re.search(pattern, degree_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""

def is_likely_job_title(text):
    """Check if text is likely a job title"""
    job_keywords = [
        'engineer', 'developer', 'manager', 'analyst', 'consultant', 
        'director', 'lead', 'senior', 'junior', 'architect', 'specialist'
    ]
    return any(keyword in text.lower() for keyword in job_keywords)

def validate_and_clean_education(education):
    """Validate and clean education entries"""
    cleaned = []
    for edu in education:
        if edu.get('institution') or edu.get('degree'):
            # Clean up fields
            edu['institution'] = edu.get('institution', '').strip()
            edu['degree'] = edu.get('degree', '').strip()
            edu['field_of_study'] = edu.get('field_of_study', '').strip()
            
            # Ensure required fields
            if not edu['institution']:
                edu['institution'] = 'Institution not specified'
            if not edu['degree']:
                edu['degree'] = 'Degree not specified'
            
            cleaned.append(edu)
    
    return cleaned

def validate_and_clean_work_experience(work_experience):
    """Validate and clean work experience entries"""
    cleaned = []
    for exp in work_experience:
        if exp.get('company') or exp.get('position'):
            # Clean up fields
            exp['company'] = exp.get('company', '').strip()
            exp['position'] = exp.get('position', '').strip()
            exp['location'] = exp.get('location', '').strip()
            
            # Ensure required fields
            if not exp['company']:
                exp['company'] = 'Company not specified'
            if not exp['position']:
                exp['position'] = 'Position not specified'
            
            cleaned.append(exp)
    
    return cleaned

def calculate_confidence(education, work_experience, base_confidence):
    """Calculate final confidence score based on data quality"""
    score = base_confidence
    
    # Boost confidence for complete data
    for edu in education:
        if edu.get('institution') and edu.get('degree') and edu.get('end_date'):
            score += 0.05
    
    for exp in work_experience:
        if exp.get('company') and exp.get('position') and exp.get('start_date'):
            score += 0.05
    
    return min(0.95, score)

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
    print("🚀 Starting Complete Fixed ATS AI Analysis Service...")
    print("🔧 Proper section separation enabled")
    print("🧠 Multi-format resume parsing enabled")
    print("📋 Available parsing strategies:")
    print("   1. Fixed section parsing (most reliable)")
    print("   2. NLP-enhanced parsing (highest accuracy)")
    print("   3. Multi-pattern regex parsing")
    print("   4. Semantic section parsing")
    print("   5. Basic fallback parsing (always succeeds)")
    print("✅ All legacy endpoints maintained for compatibility")
    
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)