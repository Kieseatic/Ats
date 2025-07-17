'''
 This is the Matching logic code
 It returns a score telling how much a resume matches to a job description
'''
from .nlp_utils import *

def calculate_score(resume_text, job):
    explanation = {}  # Dictionary to hold detailed match analytics

    # Skills score (40% weight)
    skills_score, matched_skills, unmatched_skills = calculate_skill_score(job["skills"], resume_text)
    skills_weighted = skills_score * 0.4
    explanation["Skill Match"] = {
        "score": skills_score,
        "matched": matched_skills,
        "unmatched": unmatched_skills
    }

    # Experience score (20% weight)
    experience_score, experience_explanation = calculate_experience_score(job["experience_required"], resume_text)
    experience_weighted = experience_score * 0.2
    explanation["Experience Match"] = {
        "score": experience_score,
        "details": experience_explanation
    }

    # Qualification score (30% weight)
    qualification_score, qualification_explanation = calculate_qualification_score(job["qualifications"], resume_text)
    qualification_weighted = qualification_score * 0.3
    explanation["Education Fit"] = {
        "score": qualification_score,
        "details": qualification_explanation
    }

    # Contextual similarity score (10% weight)
    contextual_score = contextual_similarity(job["responsibilities"], resume_text)
    contextual_weighted = contextual_score * 0.1
    explanation["Contextual Similarity"] = {
        "score": contextual_score
    }

    # Total weighted score
    total_score = skills_weighted + experience_weighted + qualification_weighted + contextual_weighted

    return total_score, explanation

def match_jobs(resume_text, all_job_descriptions):
    job_matches = []
    for job in all_job_descriptions:
        score, explanation = calculate_score(resume_text, job)
        job_matches.append({
            "job_id": job.get("title"),
            "score": score,
            "details": job,
            "explanation": explanation  # Add detailed analytics
        })

    # Sort job matches by score in descending order
    job_matches = sorted(job_matches, key=lambda x: x["score"], reverse=True)

    return job_matches