'''
I am using Spacy to calculate the matching score through 
looking out for matching skills, experience and qualifications 
'''
import spacy 
import re 
from sentence_transformers import SentenceTransformer, util

#Loading spacy model for word embeddings 
nlp = spacy.load("en_core_web_sm")

# Loading a sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')  # I chose this one because it takes less space and is 5 times faster than other ones

print(spacy.__version__)

# Skill matching using spaCy similarity
def skill_similarity(skill, resume_text):
    # Convert the strings into vectors
    skill_token = nlp(skill)
    resume_doc = nlp(resume_text)
    max_similarity = 0

    for token in resume_doc:
        similarity = skill_token.similarity(token)
        max_similarity = max(max_similarity, similarity)

    return max_similarity > 0.75  # Industry-standard threshold

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