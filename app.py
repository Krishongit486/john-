import os
from flask import Flask, request, jsonify, render_template
from docx import Document
import PyPDF2
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def extract_text(filepath):
    ext = filepath.split('.')[-1].lower()
    if ext == 'txt':
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    elif ext == 'docx':
        doc = Document(filepath)
        return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    elif ext == 'pdf':
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
    else:
        raise ValueError("Unsupported file type")

def query_openai(policy_text, user_inputs):
    user_description = (
        f"The user is {user_inputs['age']} years old, undergoing a procedure: '{user_inputs['procedure']}', "
        f"in location: {user_inputs['location']}, with a policy duration of {user_inputs['duration']}."
    )

    prompt = f"""
You are an insurance policy expert. Based on the following policy document and user input, determine:

1. decision: Is this procedure covered?
2. amount: Estimated claim amount (if mentioned or inferred).
3. justification: Why it is or is not covered.

Return response in valid JSON:

{{
  "decision": "...",
  "amount": "...",
  "justification": "..."
}}

Policy Document (truncated if too long):
{policy_text[:3000]}

User Details:
{user_description}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a helpful insurance claim assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"OpenAI API error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No policy document uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ['txt', 'pdf', 'docx']:
        return jsonify({"error": "Unsupported file type"}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    # User inputs
    user_inputs = {
        "age": request.form.get("age"),
        "procedure": request.form.get("procedure"),
        "location": request.form.get("location"),
        "duration": request.form.get("duration")
    }

    if not all(user_inputs.values()):
        return jsonify({"error": "Please fill in all fields."}), 400

    try:
        policy_text = extract_text(filepath)
        summary = query_openai(policy_text, user_inputs)
        return jsonify({
            "filename": file.filename,
            "user_inputs": user_inputs,
            "summary": summary
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
