'''
NLP utils with optional SpaCy support - falls back gracefully to sentence transformers only
'''
import re 
from sentence_transformers import SentenceTransformer, util

# Try to import spacy, but handle gracefully if not available
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
    print("SpaCy model loaded successfully")
except (ImportError, IOError):
    print("SpaCy not available, using sentence transformers only")
    SPACY_AVAILABLE = False

# Loading sentence transformer model for semantic similarity
model = SentenceTransformer('all-MiniLM-L6-v2')

def extract_skills_with_spacy(resume_text):
    """Use SpaCy NER to extract potential skills and entities"""
    if not SPACY_AVAILABLE:
        return []
    
    doc = nlp(resume_text)
    skills = []
    
    # Extract named entities that might be skills
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PRODUCT", "LANGUAGE", "TECHNOLOGY"]:
            skills.append(ent.text)
    
    # Extract noun phrases that might be skills
    for chunk in doc.noun_chunks:
        if len(chunk.text.split()) <= 3:  # Short phrases more likely to be skills
            skills.append(chunk.text)
    
    return list(set(skills))

def skill_similarity(skill, resume_text):
    """
    Enhanced skill matching using multiple approaches:
    1. Exact/fuzzy matching for precision
    2. Semantic similarity for broader matching
    3. SpaCy NER if available
    """
    skill_lower = skill.lower()
    resume_lower = resume_text.lower()
    
    # Method 1: Direct text matching (high precision)
    if skill_lower in resume_lower:
        return True
    
    # Method 2: Fuzzy matching for variations
    skill_variations = [
        skill_lower,
        skill_lower.replace('.', ''),
        skill_lower.replace(' ', ''),
        skill_lower.replace('-', ''),
    ]
    
    for variation in skill_variations:
        if variation in resume_lower:
            return True
    
    # Method 3: Semantic similarity using sentence transformers
    skill_embedding = model.encode([skill_lower])
    
    # Check against extracted skills if SpaCy is available
    if SPACY_AVAILABLE:
        extracted_skills = extract_skills_with_spacy(resume_text)
        for extracted_skill in extracted_skills:
            extracted_embedding = model.encode([extracted_skill.lower()])
            similarity = util.cos_sim(skill_embedding, extracted_embedding).item()
            if similarity > 0.7:  # High threshold for extracted skills
                return True
    
    # Check against entire resume text (lower threshold)
    resume_embedding = model.encode([resume_text.lower()])
    similarity = util.cos_sim(skill_embedding, resume_embedding).item()
    
    return similarity > 0.4  # Moderate threshold for full text

def calculate_skill_score(job_skills, resume_text):
    matched_skills = []
    unmatched_skills = []

    for skill in job_skills:
        if skill_similarity(skill, resume_text):
            matched_skills.append(skill)
        else:
            unmatched_skills.append(skill)

    score = (len(matched_skills) / len(job_skills)) * 100 if job_skills else 0
    return score, matched_skills, unmatched_skills

# Extract experience (using regex for better parsing)
def extract_experience(text):
    match = re.search(r'(\d+)\+?\s*(years|yrs)', text.lower())
    if match:
        return int(match.group(1))
    return 0

# Scoring the experience
def calculate_experience_score(job_experience, resume_text):
    job_exp = extract_experience(job_experience)
    resume_exp = extract_experience(resume_text)

    if resume_exp >= job_exp:
        score = 100  # Full match
        explanation = f"Candidate meets or exceeds the required experience ({resume_exp}+ years)."
    elif resume_exp >= job_exp - 1:
        score = 75
        explanation = f"Candidate has close experience ({resume_exp}+ years; job requires {job_exp}+ years)."
    elif resume_exp >= job_exp - 2:
        score = 50
        explanation = f"Candidate has some experience ({resume_exp}+ years; job requires {job_exp}+ years)."
    else:
        score = 0
        explanation = f"Candidate has insufficient experience ({resume_exp}+ years; job requires {job_exp}+ years)."

    return score, explanation

# Scoring qualifications
def calculate_qualification_score(job_qualification, resume_text):
    job_quali = job_qualification.lower()
    resume_text = resume_text.lower()

    if job_quali in resume_text:
        score = 100
        explanation = "Candidate's qualification matches the job requirement."
    elif 'bachelor' in job_quali and any(b in resume_text for b in ['bachelor', 'b.tech', 'bsc', 'beng']):
        score = 75
        explanation = "Candidate has a Bachelor's degree, partially matching the requirement."
    elif 'master' in job_quali and any(m in resume_text for m in ['master', 'msc', 'm.tech', 'meng']):
        score = 75
        explanation = "Candidate has a Master's degree, partially matching the requirement."
    else:
        score = 0
        explanation = f"Candidate's qualification does not match the requirement ({job_qualification})."

    return score, explanation

# Contextual similarity using sentence transformers
def contextual_similarity(job_description, resume_text):
    job_embedding = model.encode(job_description)
    resume_embedding = model.encode(resume_text)
    similarity = util.cos_sim(job_embedding, resume_embedding).item()
    return similarity * 100

# Technological fit (similar to skill matching)
def calculate_tech_fit(job_tools, resume_text):
    matched_tools = []
    unmatched_tools = []

    for tool in job_tools:
        if tool.lower() in resume_text.lower():
            matched_tools.append(tool)
        else:
            unmatched_tools.append(tool)

    score = (len(matched_tools) / len(job_tools)) * 100 if job_tools else 0
    return score, matched_tools, unmatched_tools