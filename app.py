# app.py
from flask import Flask, render_template, request, jsonify
import re
import PyPDF2
import docx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

app = Flask(__name__)

class ResumeComparer:
    def __init__(self):
        # Regular expressions for different fields
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        self.phone_pattern = r'(\+\d{1,3}[-.]?)?\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        
        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(stop_words='english')
        
    def extract_text(self, file):
        if isinstance(file, str):  # If input is text
            return file
            
        file_extension = file.filename.lower()
        if file_extension.endswith('.pdf'):
            return self.extract_text_from_pdf(file)
        elif file_extension.endswith('.docx'):
            return self.extract_text_from_docx(file)
        else:
            return None
    
    def extract_text_from_pdf(self, pdf_file):
        text = ""
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    
    def extract_text_from_docx(self, docx_file):
        doc = docx.Document(docx_file)
        return " ".join([paragraph.text for paragraph in doc.paragraphs])
    
    def extract_contact_info(self, text):
        email = re.search(self.email_pattern, text)
        phone = re.search(self.phone_pattern, text)
        return {
            'email': email.group(0) if email else None,
            'phone': phone.group(0) if phone else None
        }
    
    def calculate_similarity(self, text1, text2):
        # Calculate TF-IDF vectors and similarity
        tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
        return cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    
    def extract_key_sections(self, text):
        # Simple section extraction based on common headers
        sections = {
            'education': '',
            'experience': '',
            'skills': ''
        }
        
        current_section = None
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip().lower()
            if 'education' in line or 'qualification' in line:
                current_section = 'education'
                continue
            elif 'experience' in line or 'work history' in line:
                current_section = 'experience'
                continue
            elif 'skills' in line or 'expertise' in line:
                current_section = 'skills'
                continue
            
            if current_section and line:
                sections[current_section] += line + ' '
        
        return sections
    
    def compare_resumes(self, resume1, resume2, job_description):
        # Extract text from all documents
        text1 = self.extract_text(resume1)
        text2 = self.extract_text(resume2)
        job_text = self.extract_text(job_description)
        
        if not all([text1, text2, job_text]):
            return {"error": "Could not process one or more documents"}
        
        # Extract contact information
        contact1 = self.extract_contact_info(text1)
        contact2 = self.extract_contact_info(text2)
        
        # Extract key sections
        sections1 = self.extract_key_sections(text1)
        sections2 = self.extract_key_sections(text2)
        job_sections = self.extract_key_sections(job_text)
        
        # Calculate similarities for each section
        analysis = {
            'candidate1': {
                'contact': contact1,
                'overall_match': self.calculate_similarity(text1, job_text),
                'section_matches': {
                    'education': self.calculate_similarity(sections1['education'], job_sections['education']),
                    'experience': self.calculate_similarity(sections1['experience'], job_sections['experience']),
                    'skills': self.calculate_similarity(sections1['skills'], job_sections['skills'])
                }
            },
            'candidate2': {
                'contact': contact2,
                'overall_match': self.calculate_similarity(text2, job_text),
                'section_matches': {
                    'education': self.calculate_similarity(sections2['education'], job_sections['education']),
                    'experience': self.calculate_similarity(sections2['experience'], job_sections['experience']),
                    'skills': self.calculate_similarity(sections2['skills'], job_sections['skills'])
                }
            }
        }
        
        return analysis

comparer = ResumeComparer()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/compare', methods=['POST'])
def compare():
    try:
        # Get files or text from request
        resume1 = request.files.get('resume1') or request.form.get('resume1_text')
        resume2 = request.files.get('resume2') or request.form.get('resume2_text')
        job_desc = request.files.get('job_description') or request.form.get('job_description_text')
        
        if not all([resume1, resume2, job_desc]):
            return jsonify({"error": "Missing required documents"})
        
        result = comparer.compare_resumes(resume1, resume2, job_desc)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)