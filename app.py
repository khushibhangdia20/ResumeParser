from flask import Flask, render_template, request, redirect, url_for, flash
import os
import json
import re
from PyPDF2 import PdfReader
from docx import Document
from fuzzywuzzy import fuzz
from datetime import datetime

class ResumeParser:
    def __init__(self):
        # Initialize patterns and rules
        self.patterns = {
            'email': r'[\w\.-]+@[\w\.-]+\.\w+',
            'phone': r'(\+\d{1,3}[-.]?)?\d{3}[-.]?\d{3}[-.]?\d{4}',
            'education': ['Bachelor', 'Master', 'PhD', 'BSc', 'MSc', 'BE', 'BTech', 'MTech'],
            'experience_markers': ['experience', 'work history', 'employment'],
            'skills_markers': ['skills', 'technical skills', 'competencies']
        }
        
        # Skill categories and their related skills
        self.skill_database = {
            'programming_languages': {
                'keywords': ['Python', 'Java', 'JavaScript', 'C++', 'C#', 'Ruby', 'PHP', 'Swift', 'Kotlin', 'Go'],
                'weight': 1.0
            },
            'web_technologies': {
                'keywords': ['HTML', 'CSS', 'React', 'Angular', 'Vue.js', 'Node.js', 'Django', 'Flask', 'Spring'],
                'weight': 0.9
            },
            'databases': {
                'keywords': ['SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Oracle', 'Redis', 'Elasticsearch'],
                'weight': 0.8
            },
            'devops': {
                'keywords': ['Docker', 'Kubernetes', 'Jenkins', 'Git', 'AWS', 'Azure', 'GCP', 'CI/CD'],
                'weight': 0.85
            },
            'soft_skills': {
                'keywords': ['Leadership', 'Communication', 'Teamwork', 'Problem Solving', 'Project Management'],
                'weight': 0.7
            }
        }

        # Skill synonyms for better matching
        self.skill_synonyms = {
            'python': ['py', 'python3', 'python2'],
            'javascript': ['js', 'ecmascript', 'es6', 'node.js', 'nodejs'],
            'java': ['core java', 'java8', 'java11'],
            'react': ['reactjs', 'react.js', 'react native'],
            'aws': ['amazon web services', 'amazon cloud'],
            'docker': ['containerization', 'docker container'],
            'kubernetes': ['k8s', 'kube'],
            'machine learning': ['ml', 'deep learning', 'ai'],
        }

    def _extract_text_from_pdf(self, file_path):
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                text = ''
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""

    def _extract_text_from_docx(self, file_path):
        try:
            doc = Document(file_path)
            text = ''
            for paragraph in doc.paragraphs:
                text += paragraph.text + '\n'
            return text
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return ""

    def _extract_text(self, file_path):
        if file_path.lower().endswith('.pdf'):
            return self._extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            return self._extract_text_from_docx(file_path)
        return ""

    def _extract_contact_info(self, text):
        email_match = re.search(self.patterns['email'], text)
        phone_match = re.search(self.patterns['phone'], text)
        
        return {
            'email': email_match.group(0) if email_match else None,
            'phone': phone_match.group(0) if phone_match else None
        }

    def _extract_education(self, text):
        education = []
        lines = text.split('\n')
        
        for line in lines:
            for degree in self.patterns['education']:
                if degree.lower() in line.lower():
                    education.append(line.strip())
                    break
        
        return education

    def _extract_skills(self, text):
        found_skills = []
        text_lower = text.lower()
        
        # Extract skills from each category
        for category, data in self.skill_database.items():
            for skill in data['keywords']:
                # Direct match
                if skill.lower() in text_lower:
                    found_skills.append({
                        'name': skill,
                        'category': category,
                        'weight': data['weight']
                    })
                else:
                    # Check for synonyms
                    skill_lower = skill.lower()
                    if skill_lower in self.skill_synonyms:
                        for synonym in self.skill_synonyms[skill_lower]:
                            if synonym in text_lower:
                                found_skills.append({
                                    'name': skill,
                                    'category': category,
                                    'weight': data['weight'] * 0.9  # Slightly lower weight for synonym matches
                                })
                                break
        
        return found_skills

    def parse_resume(self, file_path):
        extracted_text = self._extract_text(file_path)
        if not extracted_text:
            return None
            
        contact_info = self._extract_contact_info(extracted_text)
        education = self._extract_education(extracted_text)
        skills = self._extract_skills(extracted_text)
        
        return {
            'contact_info': contact_info,
            'education': education,
            'skills': skills,
            'raw_text': extracted_text
        }

    def compare_candidate_to_job(self, candidate_data, job_requirements):
        if not candidate_data or 'skills' not in candidate_data:
            return 0, set()

        total_score = 0
        max_possible_score = 0
        matched_skills = set()
        
        required_skills = [skill.strip().lower() for skill in job_requirements['skills']]
        
        for req_skill in required_skills:
            max_possible_score += 1
            best_match_score = 0
            best_match_skill = None
            
            for candidate_skill in candidate_data['skills']:
                skill_name = candidate_skill['name'].lower()
                
                # Direct match
                if req_skill == skill_name:
                    match_score = 1.0 * candidate_skill['weight']
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_skill = candidate_skill['name']
                    continue
                
                # Synonym match
                if req_skill in self.skill_synonyms:
                    if skill_name in self.skill_synonyms[req_skill]:
                        match_score = 0.9 * candidate_skill['weight']
                        if match_score > best_match_score:
                            best_match_score = match_score
                            best_match_skill = candidate_skill['name']
                        continue
                
                # Fuzzy match for similar terms
                fuzzy_ratio = fuzz.ratio(req_skill, skill_name)
                if fuzzy_ratio > 85:
                    match_score = (fuzzy_ratio / 100) * candidate_skill['weight']
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_skill = candidate_skill['name']
            
            if best_match_skill:
                total_score += best_match_score
                matched_skills.add(best_match_skill)
        
        percentage_score = (total_score / max_possible_score * 100) if max_possible_score > 0 else 0
        return percentage_score, matched_skills

    def save_candidate_data(self, candidate_data, output_file):
        try:
            existing_data = []
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    existing_data = json.load(f)
            
            candidate_data['timestamp'] = datetime.now().isoformat()
            existing_data.append(candidate_data)
            
            with open(output_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
                
            return True
        except Exception as e:
            print(f"Error saving candidate data: {e}")
            return False

# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
OUTPUT_FILE = 'candidates.json'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize resume parser
resume_parser = ResumeParser()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Get form data
            num_candidates = int(request.form['num_candidates'])
            job_description = request.form['job_description']
            
            # Process job description
            job_skills = job_description.split(',')
            job_requirements = {
                'skills': [skill.strip() for skill in job_skills if skill.strip()]
            }
            
            # Process resumes
            candidates_data = []
            for i in range(num_candidates):
                file = request.files.get(f'resume_{i}')
                if file and file.filename and allowed_file(file.filename):
                    # Save file
                    filename = f"resume_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file.filename.rsplit('.', 1)[1]}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    
                    # Parse resume
                    parsed_data = resume_parser.parse_resume(file_path)
                    if parsed_data:
                        # Compare with job requirements
                        score, skills_match = resume_parser.compare_candidate_to_job(parsed_data, job_requirements)
                        
                        # Add results to parsed data
                        parsed_data['score'] = score
                        parsed_data['matched_skills'] = list(skills_match)
                        parsed_data['filename'] = filename
                        
                        # Save to candidates file
                        resume_parser.save_candidate_data(parsed_data, OUTPUT_FILE)
                        candidates_data.append(parsed_data)
            
            if candidates_data:
                return render_template('results.html', candidates=candidates_data)
            else:
                flash('No valid resumes were uploaded.')
                return redirect(url_for('index'))
                
        except Exception as e:
            flash(f'An error occurred: {str(e)}')
            return redirect(url_for('index'))
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)