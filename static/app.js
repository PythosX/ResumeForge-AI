let resumeFile=null,jobFile=null,analysis=null,rebuilt=null,jobText="";
const $=id=>document.getElementById(id);
function bindDrop(zone,input,callback){
  ["dragenter","dragover"].forEach(e=>$(zone).addEventListener(e,ev=>{ev.preventDefault();$(zone).classList.add("drag")}));
  ["dragleave","drop"].forEach(e=>$(zone).addEventListener(e,ev=>{ev.preventDefault();$(zone).classList.remove("drag")}));
  $(zone).addEventListener("drop",ev=>{callback(ev.dataTransfer.files[0]);});
  $(input).addEventListener("change",()=>callback($(input).files[0]));
}
function selectResume(f){if(!f)return;if(f.size>10e6){$("error").textContent="Resume must be under 10 MB.";return}resumeFile=f;$("resumeName").textContent="✓ "+f.name;$("analyzeBtn").disabled=false}
function selectJob(f){if(!f)return;if(f.size>10e6){$("error").textContent="Job description must be under 10 MB.";return}jobFile=f;$("jobName").textContent="✓ "+f.name}
bindDrop("resumeDrop","resumeInput",selectResume);bindDrop("jobDrop","jobInput",selectJob);
$("analyzeBtn").onclick=async()=>{
  if(!resumeFile)return;
  setStep(2);$("error").textContent="";
  const fd=new FormData();fd.append("resume",resumeFile);if(jobFile)fd.append("job",jobFile);
  try{
    const r=await fetch("/api/analyze",{method:"POST",body:fd}),d=await r.json();
    if(!r.ok)throw Error(d.error||"Analysis failed");
    analysis=d;jobText=d.job_text||"";renderAnalysis(d);$("uploadStage").classList.add("hidden");$("analysisStage").classList.remove("hidden");scrollTo({top:0,behavior:"smooth"});
  }catch(e){$("error").textContent=e.message;setStep(1)}
};
function setStep(n){document.querySelectorAll(".step").forEach(x=>x.classList.toggle("active",Number(x.dataset.step)<=n))}
function renderAnalysis(d){
  $("score").textContent=d.ats_score??d.score??0;$("scoreRing").style.setProperty("--score",(d.ats_score??d.score??0)+"%");
  const m=d.match_score;
  $("matchScore").textContent=m==null?"—":m;$("matchRing").style.setProperty("--score",(m||0)+"%");
  $("scoreLabel").textContent=(d.ats_score??d.score??0)>=80?"Strong":(d.ats_score??d.score??0)>=60?"Good start":"Needs improvement";
  $("matchLabel").textContent=m==null?"No job added":m>=80?"Strong match":m>=60?"Moderate match":"Low match";
  $("headline").textContent=d.headline||d.summary||"Your resume has been analyzed.";
  $("wordCount").textContent=d.word_count;$("bulletCount").textContent=d.bullet_count;$("sectionCount").textContent=Object.values(d.sections||{}).filter(Boolean).length;
  $("provider").textContent=d.ai_provider==="ollama"?"Ollama":d.ai_provider==="groq"?"Groq":"Rules";
  $("strengths").innerHTML=(d.strengths||[]).map(x=>`<div class="item">✓ ${esc(x)}</div>`).join("");
  $("issues").innerHTML=(d.issues||[]).map(x=>`<div class="item ${x.severity||"medium"}"><b>${esc(x.title)}</b>${esc(x.detail)}</div>`).join("")||'<div class="item">No major issues detected.</div>';
  $("improvements").innerHTML=(d.improvements||[]).map(x=>`<div class="improvement">→ ${esc(x)}</div>`).join("");
  $("matched").innerHTML=(d.matched_keywords||[]).map(x=>`<span class="chip">${esc(x)}</span>`).join("")||'<span class="item">No semantic matches detected.</span>';
  $("missing").innerHTML=(d.missing_keywords||[]).map(x=>`<span class="chip">${esc(x)}</span>`).join("")||'<span class="item">No missing keywords detected.</span>';
  renderPaper(d.parsed,"originalPaper");
}
function goRebuild(){setStep(3);$("analysisStage").classList.add("hidden");$("rebuildStage").classList.remove("hidden");scrollTo({top:0,behavior:"smooth"})}
async function rebuild(){
  const role=$("targetRole").value;
  const r=await fetch("/api/rebuild",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({parsed:analysis.parsed,job:jobText,target_role:role})});
  const d=await r.json();rebuilt=d.resume;renderPaper(analysis.parsed,"originalPaper");renderPaper(rebuilt,"rebuiltPaper");
  $("compare").classList.remove("hidden");$("exportBar").classList.remove("hidden");setStep(4);
}
function section(t,v){if(!v||!v.length)return"";return `<h3>${t}</h3>`+(Array.isArray(v)?`<ul>${v.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:`<p>${esc(v)}</p>`)}
function renderPaper(r,id){$(id).innerHTML=`<h1>${esc(r.name||"Your Name")}</h1><div class="resume-contact">${esc([r.email,r.phone].filter(Boolean).join(" • "))}</div>${section("PROFESSIONAL SUMMARY",r.summary)}${section("EXPERIENCE",r.experience)}${section("SKILLS",r.skills)}${section("EDUCATION",r.education)}${section("PROJECTS",r.projects)}${section("CERTIFICATIONS",r.certifications)}`}
async function downloadPDF(){
 const r=await fetch("/api/download/pdf",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({resume:rebuilt})});
 if(!r.ok)return alert("PDF export failed.");
 const b=await r.blob(),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="rebuilt_resume.pdf";a.click();URL.revokeObjectURL(a.href);
}
function resetAll(){location.reload()}
function esc(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}
