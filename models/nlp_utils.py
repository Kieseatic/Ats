'''
NLP utils - MINIMAL VERSION (No spaCy, No sentence-transformers)
Pure Python text processing for deployment-safe ATS functionality
'''
import re
from difflib import SequenceMatcher

def skill_similarity(skill, resume_text):
    """
    Lightweight skill matching using only built-in Python libraries
    """
    skill_lower = skill.lower().strip()
    resume_lower = resume_text.lower()
    
    # Method 1: Direct exact match
    if skill_lower in resume_lower:
        return True
    
    # Method 2: Handle common variations
    skill_variations = [
        skill_lower,
        skill_lower.replace('.', ''),
        skill_lower.replace(' ', ''),
        skill_lower.replace('-', ''),
        skill_lower.replace('+', 'plus'),
        skill_lower.replace('#', 'sharp'),
    ]
    
    for variation in skill_variations:
        if variation in resume_lower:
            return True
    
    # Method 3: Tech skill aliases
    tech_aliases = {
        'javascript': ['js', 'ecmascript'],
        'js': ['javascript'],
        'typescript': ['ts'],
        'ts': ['typescript'],
        'react': ['reactjs', 'react.js'],
        'node': ['nodejs', 'node.js'],
        'python': ['py', 'python3'],
        'c++': ['cpp', 'cplusplus'],
        'c#': ['csharp', 'c-sharp'],
        'aws': ['amazon web services'],
        'gcp': ['google cloud platform', 'google cloud'],
        'docker': ['containerization'],
        'kubernetes': ['k8s'],
        'postgresql': ['postgres'],
        'mongodb': ['mongo'],
        'mysql': ['my sql'],
        'html5': ['html'],
        'css3': ['css'],
        'restful': ['rest api', 'rest'],
        'graphql': ['graph ql'],
        'git': ['version control'],
        'jenkins': ['ci/cd'],
        'angular': ['angularjs']
    }
    
    # Check if skill has aliases
    if skill_lower in tech_aliases:
        for alias in tech_aliases[skill_lower]:
            if alias in resume_lower:
                return True
    
    # Reverse check - if skill is an alias
    for main_skill, aliases in tech_aliases.items():
        if skill_lower in aliases and main_skill in resume_lower:
            return True
    
    # Method 4: Partial matching for compound skills
    skill_words = skill_lower.split()
    if len(skill_words) > 1:
        matches = sum(1 for word in skill_words if word in resume_lower and len(word) > 2)
        return matches >= len(skill_words) * 0.7  # 70% of words must match
    
    # Method 5: Similar spelling check for single words
    if len(skill_lower) > 3:
        resume_words = re.findall(r'\b\w{3,}\b', resume_lower)
        for word in resume_words:
            if SequenceMatcher(None, skill_lower, word).ratio() > 0.85:
                return True
    
    return False

def calculate_skill_score(job_skills, resume_text):
    """Calculate skill match score using lightweight matching"""
    if not job_skills:
        return 0, [], []
    
    matched_skills = []
    unmatched_skills = []

    for skill in job_skills:
        if skill_similarity(skill, resume_text):
            matched_skills.append(skill)
        else:
            unmatched_skills.append(skill)

    score = (len(matched_skills) / len(job_skills)) * 100
    return score, matched_skills, unmatched_skills

def extract_experience(text):
    """Extract years of experience using regex patterns"""
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
        r'(?:experience|exp).*?(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\s*(?:year|yr)\s*(?:experience|exp)',
        r'over\s+(\d+)\s*(?:years?|yrs?)',
        r'more\s+than\s+(\d+)\s*(?:years?|yrs?)',
        r'(\d+)\+\s*(?:years?|yrs?)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return int(match.group(1))
    
    return 0

def calculate_experience_score(job_experience, resume_text):
    """Score experience match"""
    job_exp = extract_experience(job_experience) if job_experience else 0
    resume_exp = extract_experience(resume_text)

    if job_exp == 0:
        return 100, "No specific experience requirement mentioned."

    if resume_exp >= job_exp:
        score = 100
        explanation = f"Candidate meets/exceeds required experience ({resume_exp}+ years vs {job_exp}+ required)."
    elif resume_exp >= job_exp - 1:
        score = 75
        explanation = f"Candidate has close experience ({resume_exp}+ years vs {job_exp}+ required)."
    elif resume_exp >= job_exp - 2:
        score = 50
        explanation = f"Candidate has some experience ({resume_exp}+ years vs {job_exp}+ required)."
    else:
        score = 25
        explanation = f"Candidate has limited experience ({resume_exp}+ years vs {job_exp}+ required)."

    return score, explanation

def calculate_qualification_score(job_qualification, resume_text):
    """Score qualification match using regex patterns"""
    if not job_qualification or not job_qualification.strip():
        return 100, "No specific qualification requirement."
    
    job_quali = job_qualification.lower()
    resume_lower = resume_text.lower()

    # Exact match
    if job_quali in resume_lower:
        return 100, "Perfect qualification match found."
    
    # Degree level matching patterns
    degree_patterns = {
        'bachelor': [
            r'\bbachelor\b', r'\bb\.?\s*a\.?\b', r'\bb\.?\s*s\.?\b', 
            r'\bb\.?\s*tech\b', r'\bb\.?\s*sc\.?\b', r'\bb\.?\s*eng\.?\b',
            r'\bundergraduate\b'
        ],
        'master': [
            r'\bmaster\b', r'\bm\.?\s*a\.?\b', r'\bm\.?\s*s\.?\b',
            r'\bm\.?\s*tech\b', r'\bm\.?\s*sc\.?\b', r'\bm\.?\s*eng\.?\b',
            r'\bmba\b', r'\bgraduate\b'
        ],
        'phd': [
            r'\bphd\b', r'\bph\.?\s*d\.?\b', r'\bdoctorate\b', r'\bdoctoral\b'
        ],
        'diploma': [
            r'\bdiploma\b', r'\bcertificate\b', r'\bcert\.?\b'
        ]
    }
    
    # Check for degree level matches
    for degree_type, patterns in degree_patterns.items():
        if degree_type in job_quali:
            for pattern in patterns:
                if re.search(pattern, resume_lower):
                    return 80, f"Matching {degree_type} level qualification found."
    
    # Field of study matching
    fields = [
        'computer', 'software', 'engineering', 'science', 'technology',
        'business', 'management', 'information', 'mathematics', 'physics'
    ]
    
    job_fields = [field for field in fields if field in job_quali]
    resume_fields = [field for field in fields if field in resume_lower]
    
    common_fields = set(job_fields) & set(resume_fields)
    if common_fields:
        return 60, f"Related field qualification found: {', '.join(common_fields)}."
    
    # Check for any education mentions
    education_keywords = [
        'university', 'college', 'institute', 'school', 'education',
        'degree', 'graduated', 'studied'
    ]
    
    if any(keyword in resume_lower for keyword in education_keywords):
        return 40, "Some educational background found."
    
    return 20, f"No matching qualification found for requirement: {job_qualification}."

def contextual_similarity(job_description, resume_text):
    """Basic contextual similarity using keyword overlap"""
    if not job_description or not resume_text:
        return 0
    
    # Extract meaningful words (remove common stop words)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 
        'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }
    
    job_words = set(re.findall(r'\b\w{3,}\b', job_description.lower()))
    resume_words = set(re.findall(r'\b\w{3,}\b', resume_text.lower()))
    
    job_words = job_words - stop_words
    resume_words = resume_words - stop_words
    
    if not job_words:
        return 0
    
    # Calculate intersection
    overlap = len(job_words & resume_words)
    similarity = (overlap / len(job_words)) * 100
    
    return min(similarity, 100)  # Cap at 100%

def calculate_tech_fit(job_tools, resume_text):
    """Calculate technology fit using simple matching"""
    if not job_tools:
        return 100, [], []
    
    matched_tools = []
    unmatched_tools = []

    for tool in job_tools:
        if skill_similarity(tool, resume_text):
            matched_tools.append(tool)
        else:
            unmatched_tools.append(tool)

    score = (len(matched_tools) / len(job_tools)) * 100
    return score, matched_tools, unmatched_tools