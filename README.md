# ResumeForge AI — Production-ready hosted version

A Flask + HTML/CSS/JS SaaS resume analyzer/rebuilder.

## What is actually free and unlimited?

There is **no reputable hosted LLM API that is both free and unlimited**. Groq's free plan has explicit RPM/RPD/TPM/TPD limits. Gemini also has model-specific free-tier rate limits. Do not design a public app around the claim "unlimited free API."

For a public demo, this project uses **Groq's free tier** through a server-side API key. For genuinely unlimited inference, run an open model on hardware you control; the limitation then becomes your hardware rather than a provider's free API quota.

## 1. Create your Groq API key

Go to the official Groq API Keys page:

https://console.groq.com/keys

Create a key, copy it immediately, and keep it private.

Never put the key in:
- `static/app.js`
- HTML
- browser JavaScript
- GitHub
- screenshots
- README files

## 2. Local setup

Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` from `.env.example` and add:

```env
GROQ_API_KEY=gsk_your_real_key
GROQ_MODEL=llama-3.3-70b-versatile
```

For local development, load `.env` with your shell/IDE, or set the environment variable before starting Flask. The code reads `GROQ_API_KEY` from the environment.

PowerShell:

```powershell
$env:GROQ_API_KEY="gsk_your_real_key"
$env:GROQ_MODEL="llama-3.3-70b-versatile"
python app.py
```

Open:

http://127.0.0.1:5000

## 3. Test the AI

Upload:
- Resume PDF/DOCX
- Optional job-description PDF/DOCX

Then:
1. Analyze
2. Review ATS score
3. Review job match
4. Review missing keywords
5. Enter target role
6. Generate rebuilt resume
7. Download PDF

## 4. GitHub

Create a public repository, for example:

`resume-analyser-rebuilder`

Then:

```bash
git init
git add .
git commit -m "Build ResumeForge AI"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/resume-analyser-rebuilder.git
git push -u origin main
```

Before pushing:
- Replace `YOUR_GITHUB_USERNAME` in `templates/index.html`.
- Make sure `.env` is ignored.
- Never commit a real API key.

## 5. Deploy online with Render

Render supports Flask web services and has a free option for testing/hobby projects.

1. Push the repository to GitHub.
2. Open Render.
3. Create `New → Web Service`.
4. Connect your GitHub repository.
5. Build command:

```text
pip install -r requirements.txt
```

6. Start command:

```text
gunicorn app:app
```

7. Add Environment Variables:
   - `GROQ_API_KEY` = your Groq key
   - `GROQ_MODEL` = `llama-3.3-70b-versatile`
8. Deploy.

Do not put the API key in GitHub.

## 6. Render free-tier reality

Render's free web service is useful for demos and hobby projects but has limitations and can spin down after inactivity. It is not a promise of 24/7 production availability.

## 7. Security before public launch

For a real public service, add:
- authentication
- rate limiting per visitor
- request logging without storing resume contents
- automatic temporary-file deletion
- strict file type validation
- virus/malware scanning
- CSRF protection
- privacy policy and consent
- maximum prompt/text length
- provider error handling
- abuse prevention

## 8. Privacy

Resumes contain personal information. Tell users what is sent to the AI provider and how long you retain it. This project deletes temporary uploaded files after extraction, but you should review the provider's current data/privacy terms before public launch.

## Architecture

Browser
→ Flask
→ PDF/DOCX extraction
→ Groq API
→ JSON analysis/rebuild
→ SaaS dashboard
→ PDF export

The API key stays on the server.
