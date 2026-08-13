import io, json, os, re, uuid
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER
except ImportError:
    SimpleDocTemplate = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED = {"pdf", "docx"}
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def extract_pdf(path):
    if not PyPDF2:
        raise RuntimeError("Install PyPDF2.")
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_docx(path):
    if not Document:
        raise RuntimeError("Install python-docx.")
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def extract_text(path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    raise RuntimeError("Only PDF and DOCX are supported.")

def extract_uploaded_text(field_name):
    if field_name not in request.files:
        return ""
    f = request.files[field_name]
    if not f or not f.filename:
        return ""
    ext = Path(f.filename).suffix.lower()
    if ext not in {".pdf", ".docx"}:
        raise RuntimeError(f"{field_name}: only PDF and DOCX are supported.")
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
    f.save(path)
    try:
        return extract_text(path)
    finally:
        try: path.unlink()
        except OSError: pass

def email(text):
    m = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    return m.group(0) if m else ""

def phone(text):
    m = re.search(r'(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)', text)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""

def first_name(text):
    for line in [x.strip() for x in text.splitlines() if x.strip()][:8]:
        if len(line.split()) <= 5 and not any(c in line for c in "@0123456789"):
            return line
    return "Your Name"

def section_presence(text):
    low = text.lower()
    groups = {
        "Summary": ["summary", "profile", "objective"],
        "Experience": ["experience", "work history", "employment"],
        "Education": ["education", "academic"],
        "Skills": ["skills", "technical skills", "core competencies"],
        "Projects": ["projects", "portfolio"],
        "Certifications": ["certification", "certifications", "licenses"],
    }
    return {k: any(x in low for x in v) for k,v in groups.items()}

def rule_analysis(text):
    low = text.lower()
    words = re.findall(r"\b[\w+#.-]+\b", text)
    bullets = len(re.findall(r"(?m)^\s*(?:[-•▪◦*]|\d+[.)])\s+", text))
    action_words = ["led","built","created","developed","designed","managed","improved","increased","reduced","optimized","automated","delivered","implemented","launched","analyzed","achieved","coordinated","engineered","mentored","owned"]
    action_hits = sum(len(re.findall(r"\b"+re.escape(w)+r"\b", low)) for w in action_words)
    numbers = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    sections = section_presence(text)

    score = 45 + min(12, len(words)//55)
    score += 8 if email(text) else -4
    score += 8 if phone(text) else -4
    score += 8 if sections["Experience"] else -8
    score += 6 if sections["Education"] else -4
    score += 6 if sections["Skills"] else -5
    score += 5 if bullets >= 5 else -2
    score += min(7, numbers)
    score += min(5, action_hits//3)
    score = max(0, min(100, score))

    issues=[]
    improvements=[]
    checks=[
        (not email(text),"Missing email","Add a professional email in the header.","contact"),
        (not phone(text),"Missing phone","Add a phone number in the header.","contact"),
        (not sections["Summary"],"No professional summary","Add a targeted 2–4 line summary.","content"),
        (not sections["Experience"],"Experience section not detected","Use a clear Professional Experience heading.","structure"),
        (not sections["Skills"],"Skills section not detected","Add role-specific tools, technologies, and competencies.","keywords"),
        (bullets < 5,"Too few bullet points","Convert responsibilities into concise achievement bullets.","impact"),
        (numbers < 2,"Low use of measurable results","Quantify outcomes such as revenue, time, users, accuracy, cost, or scale.","impact"),
        (action_hits < 3,"Weak action language","Start bullets with strong verbs such as built, led, optimized, launched, or improved.","language"),
        (len(words) > 1000,"Resume may be too long","Remove repetition and keep the most relevant evidence.","structure"),
    ]
    for condition,title,fix,category in checks:
        if condition:
            issues.append({"title":title,"detail":fix,"category":category})
            improvements.append(fix)

    return {
        "score":score, "name":first_name(text), "email":email(text), "phone":phone(text),
        "word_count":len(words), "bullet_count":bullets, "sections":sections,
        "issues":issues, "improvements":improvements,
        "strengths":[
            x for x in [
                "Contact details are identifiable." if email(text) and phone(text) else "",
                "Professional experience section is present." if sections["Experience"] else "",
                "Education section is present." if sections["Education"] else "",
                "Skills section is present." if sections["Skills"] else "",
                "Uses bullet formatting." if bullets >= 5 else "",
                "Contains measurable evidence." if numbers >= 2 else "",
            ] if x
        ] or ["Source content is available for rebuilding."]
    }

def llm_call(prompt):
    """Hosted AI call. Keep the key server-side in GROQ_API_KEY."""
    if not GROQ_API_KEY:
        return None, "rules"
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional ATS resume analyst. Return only valid JSON when requested."
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.15,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        if r.ok:
            return r.json()["choices"][0]["message"]["content"], "groq"
        if r.status_code == 429:
            raise RuntimeError("AI free-tier rate limit reached. Please try again later.")
        raise RuntimeError(f"Groq API error: {r.status_code}")
    except requests.RequestException as exc:
        raise RuntimeError(f"AI provider is unavailable: {exc}")

def parse_resume(text):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    aliases={
        "summary":["summary","profile","objective"],
        "experience":["experience","work history","employment"],
        "education":["education","academic"],
        "skills":["skills","technical skills","core competencies"],
        "projects":["projects","portfolio"],
        "certifications":["certification","certifications","licenses"]
    }
    buckets={k:[] for k in aliases}; current=None
    for line in lines:
        low=line.lower().strip(" :-")
        found=None
        for key, vals in aliases.items():
            if low in vals or any(low.startswith(v+":") for v in vals):
                found=key; break
        if found:
            current=found; continue
        if current: buckets[current].append(line)
    bullets=[x.lstrip("-•* ").strip() for x in buckets["experience"] if x.startswith(("-","•","*"))]
    return {
        "name":first_name(text),"email":email(text),"phone":phone(text),
        "summary":" ".join(buckets["summary"])[:900] or "Results-driven professional with experience delivering high-quality work and measurable outcomes.",
        "experience":(bullets or buckets["experience"])[:15],
        "skills":[x.strip("•-* ") for x in buckets["skills"] if x][:30],
        "education":buckets["education"][:10],
        "projects":buckets["projects"][:10],
        "certifications":buckets["certifications"][:10]
    }

def ai_analysis(resume, job):
    prompt=f"""
You are an expert ATS resume reviewer. Return ONLY valid JSON.
Analyze the resume against the job description when provided.
Resume:
{resume[:18000]}

Job description:
{job[:12000] if job else "No job description provided."}

Return this exact shape:
{{
 "ats_score": 0,
 "match_score": 0,
 "headline": "short verdict",
 "summary": "detailed concise assessment",
 "strengths": ["..."],
 "issues": [{{"title":"...","detail":"...","severity":"high|medium|low"}}],
 "improvements": ["..."],
 "missing_keywords": ["..."],
 "matched_keywords": ["..."],
 "section_scores": {{
   "content": 0,
   "impact": 0,
   "keywords": 0,
   "format": 0,
   "clarity": 0
 }}
}}
Do not invent facts about the candidate. Score only what is supported.
"""
    raw, provider=llm_call(prompt)
    if not raw: return None, "rules"
    try:
        return json.loads(raw), provider
    except Exception:
        return None, provider

def ai_rebuild(parsed, job, role):
    prompt=f"""
Return ONLY valid JSON. Rebuild this resume using ONLY information already present.
Improve wording, hierarchy, ATS keyword alignment, and achievement framing without inventing employers, dates, degrees, technologies, metrics, or accomplishments.
Target role: {role or "Not specified"}
Job description:
{job[:10000] if job else "Not provided"}
Source resume JSON:
{json.dumps(parsed, ensure_ascii=False)}

Return exactly:
{{
 "name":"","email":"","phone":"","summary":"",
 "experience":[""],"skills":[""],"education":[""],"projects":[""],"certifications":[]
}}
"""
    raw, provider=llm_call(prompt)
    if not raw: return None, "rules"
    try: return json.loads(raw), provider
    except Exception: return None, provider

@app.get("/health")
def health():
    return jsonify({"status":"ok","ai_configured":bool(GROQ_API_KEY)})

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/analyze")
def analyze_api():
    try:
        resume=extract_uploaded_text("resume")
        job=extract_uploaded_text("job") if "job" in request.files and request.files["job"].filename else ""
        if not resume.strip(): return jsonify({"error":"No readable resume text found."}),400
        rules=rule_analysis(resume)
        parsed=parse_resume(resume)
        ai, provider=ai_analysis(resume,job)
        if ai:
            result={**rules, **ai}
            result["ai_provider"]=provider
        else:
            result={**rules,"match_score":0 if not job else None,"headline":"Rule-based analysis complete","summary":"Local analysis is available. Start Ollama for deeper semantic analysis.","section_scores":{"content":rules["score"],"impact":rules["score"],"keywords":rules["score"],"format":rules["score"],"clarity":rules["score"]},"missing_keywords":[],"matched_keywords":[],"ai_provider":"rules"}
        result["parsed"]=parsed
        result["has_job"]=bool(job.strip())
        result["job_text"]=job[:12000]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.post("/api/rebuild")
def rebuild_api():
    data=request.get_json(force=True)
    parsed=data.get("parsed",{})
    job=data.get("job","")
    role=data.get("target_role","")
    rebuilt,provider=ai_rebuild(parsed,job,role)
    if not rebuilt:
        rebuilt=dict(parsed)
        rebuilt["experience"]=[
            x if re.match(r"^(Led|Built|Developed|Designed|Managed|Improved|Created|Implemented|Optimized|Delivered|Automated|Analyzed)\b",x,re.I)
            else "Delivered "+x[:1].lower()+x[1:] for x in rebuilt.get("experience",[]) if x
        ]
        provider="rules"
    return jsonify({"resume":rebuilt,"provider":provider})

@app.post("/api/download/pdf")
def pdf_api():
    data=request.get_json(force=True); r=data.get("resume",{})
    if not SimpleDocTemplate: return jsonify({"error":"Install reportlab."}),500
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=40)
    styles=getSampleStyleSheet()
    styles["Title"].alignment=TA_CENTER
    story=[Paragraph(r.get("name","Your Name"),styles["Title"]),
           Paragraph(" • ".join(x for x in [r.get("email",""),r.get("phone","")] if x),styles["Normal"]),
           Spacer(1,12)]
    def section(title,body):
        if not body:return
        story.append(Paragraph(title,styles["Heading2"]))
        if isinstance(body,list):
            for x in body: story.append(Paragraph("• "+x,styles["BodyText"]))
        else: story.append(Paragraph(body,styles["BodyText"]))
        story.append(Spacer(1,7))
    section("PROFESSIONAL SUMMARY",r.get("summary",""))
    section("EXPERIENCE",r.get("experience",[]))
    section("SKILLS",r.get("skills",[]))
    section("EDUCATION",r.get("education",[]))
    section("PROJECTS",r.get("projects",[]))
    section("CERTIFICATIONS",r.get("certifications",[]))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setFont("Helvetica",8); canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0]/2,20,"Generated with ResumeForge AI"); canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer); buf.seek(0)
    return send_file(buf,as_attachment=True,download_name="rebuilt_resume.pdf",mimetype="application/pdf")

if __name__=="__main__":
    app.run(debug=True)
