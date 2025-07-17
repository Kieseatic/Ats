import json

# Parsing function for JSON files
def parse_job_description(job_data):
    title = job_data.get("title", "No title provided")
    skills = job_data.get("skills", [])
    qualifications = job_data.get("qualifications", "")
    experience_required = job_data.get("experience_required", "Not specified")
    responsibilities = job_data.get("responsibilities", "")

    return {
        "title": title,
        "skills": skills,
        "qualifications": qualifications,
        "experience_required": experience_required,
        "responsibilities": responsibilities
    }

# Parsing function for Text files
def parse_text_job_description(content):
    # Split content into lines for easier parsing
    lines = content.splitlines()
    
    # Initialize parsed fields
    title = "No title provided"
    skills = []
    qualifications = ""
    experience_required = ""
    responsibilities = ""

    # Simple keyword-based parsing logic
    for line in lines:
        line_lower = line.lower()
        if "title:" in line_lower:
            title = line.split(":", 1)[1].strip()
        elif "skills:" in line_lower:
            skills = [skill.strip() for skill in line.split(":", 1)[1].split(",")]
        elif "qualifications:" in line_lower:
            qualifications = line.split(":", 1)[1].strip()
        elif "experience:" in line_lower or "years" in line_lower:
            experience_required = line.strip()
        elif "responsibilities:" in line_lower:
            responsibilities = line.split(":", 1)[1].strip()

    return {
        "title": title,
        "skills": skills,
        "qualifications": qualifications,
        "experience_required": experience_required,
        "responsibilities": responsibilities
    }
