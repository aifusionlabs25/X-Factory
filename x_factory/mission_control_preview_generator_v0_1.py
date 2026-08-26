"""Generate a provider-free local Mission Control preview after governed gates pass."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any


FILES = ("index.html", "styles.css", "app.js")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object: {path.name}")
    return value


def _empty_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir() or any(resolved.iterdir()):
        raise PermissionError("Preview output must be an existing empty directory")
    return resolved


def generate(owner_path: Path, blueprint_path: Path, output_path: Path) -> tuple[str, ...]:
    if os.environ.get("X_FACTORY_NETWORK_DISABLED") != "1":
        raise PermissionError("X_FACTORY_NETWORK_DISABLED=1 is required")
    owner = _load(owner_path)
    blueprint = _load(blueprint_path)
    if owner.get("run_id") != blueprint.get("run_id"):
        raise ValueError("Owner intake and blueprint mission IDs differ")
    if blueprint.get("authority", {}).get("deployment_authorized") is not False:
        raise PermissionError("Preview accepts contained, non-deployable blueprints only")
    output = _empty_output(output_path)
    data = {"owner": owner, "blueprint": blueprint, "preview": {"portrait": None}}
    experience = owner.get("experience_shell") or blueprint.get("raw_intake", {}).get("experience_shell") or {}
    avatar = experience.get("avatar", {})
    preview_portrait = None
    if avatar.get("existing_avatar_id") == "edf6fdcb-acab-44b8-b974-ded72665ee26":
        portrait_source = Path(__file__).resolve().parents[1] / "assets/anam/mia-support-guide/portrait.webp"
        if portrait_source.is_file():
            preview_portrait = "assets/anam-mia-portrait.webp"
            portrait_target = output / preview_portrait
            portrait_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(portrait_source, portrait_target)
            data["preview"]["portrait"] = preview_portrait

    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>X-Factory Mission Control — Local Draft</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="grain"></div>
  <header class="masthead">
    <div class="brand-lockup"><span class="brand-mark">X</span><div><b>X-FACTORY</b><small>MISSION CONTROL / LOCAL DRAFT</small></div></div>
    <div class="safety"><i></i> CONTAINED · NO EXTERNAL ACTIONS</div>
  </header>
  <main>
    <section class="hero">
      <div class="eyebrow">ASSEMBLY ORDER <span>001</span></div>
      <h1>Describe the agent.<br><em>The floor builds the rest.</em></h1>
      <p>One brief enters. Four named specialists turn it into a reviewed, testable X-Agent draft.</p>
    </section>

    <section class="workbench">
      <form id="mission-form" class="brief-card">
        <div class="card-head"><span>01</span><div><b>OWNER BRIEF</b><small>The only panel you fill out</small></div></div>
        <label>Purpose<textarea id="purpose" rows="3"></textarea></label>
        <div class="two-col"><label>Agent / client<input id="client"></label><label>Personality<input id="personality"></label></div>
        <label>Must accomplish<input id="must"></label>
        <label>Never do<input id="never"></label>
        <fieldset class="presence-choice"><legend>How should this agent appear?</legend><div class="presence-options"><button type="button" data-presence="EXISTING_ANAM">Existing ANAM</button><button type="button" data-presence="CREATE_NEW_ANAM">Create ANAM</button><button type="button" data-presence="STOCK_IMAGE">Stock image</button><button type="button" data-presence="TEXT_ONLY">Text only</button></div><small id="presence-note">Choose now or let the Factory recommend one later.</small></fieldset>
        <button type="submit"><span>RUN THE FACTORY</span><b>→</b></button>
        <p class="micro">Replay only · this preview makes no provider or network calls.</p>
      </form>

      <div class="floor-card">
        <div class="card-head"><span>02</span><div><b>FACTORY FLOOR</b><small id="floor-status">Ready for a contained replay</small></div><strong id="progress">0%</strong></div>
        <div class="rail"><div id="rail-fill"></div></div>
        <div class="stations" id="stations">
          <article data-station="0"><div class="portrait atlas">A</div><div><small>INTAKE FOREMAN</small><h3>Atlas</h3><p>Clarifies the brief and locks requirements.</p></div><mark>QUEUED</mark></article>
          <article data-station="1"><div class="portrait aria">A</div><div><small>SYSTEM ARCHITECT</small><h3>Aria</h3><p>Designs the agent and selects components.</p></div><mark>QUEUED</mark></article>
          <article data-station="2"><div class="portrait vera">V</div><div><small>QUALITY GATE</small><h3>Vera</h3><p>Challenges evidence, safety, and completeness.</p></div><mark>QUEUED</mark></article>
          <article data-station="3"><div class="portrait mason">M</div><div><small>MASTER BUILDER</small><h3>Mason</h3><p>Turns the approved blueprint into a draft.</p></div><mark>QUEUED</mark></article>
        </div>
      </div>
    </section>

    <section class="output-deck">
      <div class="deck-head"><div><span>03</span><b>FINISHED DRAFT</b></div><nav><button class="active" data-tab="summary">Agent card</button><button data-tab="concierge">Live preview</button><button data-tab="evidence">Build record</button></nav></div>
      <div id="summary" class="tab active"><div class="agent-poster"><div><small>GENERATED X-AGENT</small><h2 id="agent-name"></h2><p id="agent-role"></p></div><div class="seal">DRAFT<br><b>READY</b></div></div><div class="spec-grid"><div><small>PRIMARY JOB</small><p id="primary-job"></p></div><div><small>SELECTED COMPONENT</small><p id="component"></p></div><div><small>HARD BOUNDARIES</small><ul id="boundaries"></ul></div><div><small>SUCCESS TESTS</small><ul id="tests"></ul></div></div></div>
      <div id="concierge" class="tab"><div class="concierge-shell"><aside><small>SYNTHETIC LOCAL DRAFT</small><div class="avatar-stage" id="avatar-stage"><img id="avatar-reference" alt="Factory-recommended ANAM persona"><div class="avatar-head"><i></i><b></b></div><span id="avatar-mode">PRESENCE NOT SELECTED</span></div><h2 id="concierge-name"></h2><p id="persona-reference"></p><p><b id="ai-label">AI concierge</b> · No booking. No sending. No stored data.</p><div id="faq-buttons"></div></aside><div class="conversation"><div class="message bot" id="opening-message">Hi — I can answer approved questions and help prepare a request for staff review. What would you like to do?</div><div id="messages"></div><div class="composer"><input id="chat-input" placeholder="Ask an approved question…"><button id="send-chat">SEND</button></div></div><div class="handoff"><small>LIVE HANDOFF</small><div id="handoff-fields"></div><button id="copy-handoff">COPY JSON</button><button class="ghost" id="reset-preview">RESET</button></div></div></div>
      <div id="evidence" class="tab"><div class="evidence-grid"><div><small>GOVERNANCE</small><b>X_FACTORY_GOVERNED_RUN_V0_1</b><p>Disclosure and owner approval hashes are bound into every stage payload.</p></div><div><small>MODEL ROUTE</small><b>gpt-5.6-luna / low</b><p>Maximum one request per station. No retry.</p></div><div><small>TOOLS</small><b>0</b><p>No MCP, memory, delegation, or external actions.</p></div><div><small>OUTPUT</small><b>CONTAINED DRAFT</b><p>No installation, deployment, release, or production authority.</p></div></div></div>
    </section>
  </main>
  <footer><span>X-FACTORY / GOVERNED ASSEMBLY SYSTEM</span><span id="mission-id"></span></footer>
  <script src="app.js"></script>
</body>
</html>
"""

    css = """:root{--ink:#161814;--paper:#eee9dc;--signal:#f04b24;--acid:#d8ed56;--steel:#75786f;--line:#2c2e28;--blue:#50768e;--gold:#bc8c35}*{box-sizing:border-box}html{background:var(--ink);color:var(--ink);font-family:"Bahnschrift Condensed","Arial Narrow",sans-serif}body{margin:0;background:var(--paper);min-height:100vh}.grain{position:fixed;inset:0;pointer-events:none;z-index:10;opacity:.09;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}.masthead{height:76px;background:var(--ink);color:var(--paper);display:flex;align-items:center;justify-content:space-between;padding:0 4vw;border-bottom:4px solid var(--signal)}.brand-lockup{display:flex;align-items:center;gap:13px}.brand-mark{display:grid;place-items:center;width:42px;height:42px;background:var(--signal);font:900 32px/1 Georgia,serif;transform:rotate(-3deg)}.brand-lockup b{font-size:20px;letter-spacing:.15em}.brand-lockup small{display:block;color:#a6a99f;letter-spacing:.16em;font-size:9px}.safety{font-size:10px;letter-spacing:.12em;border:1px solid #51544c;padding:9px 12px}.safety i{display:inline-block;width:7px;height:7px;background:var(--acid);border-radius:50%;margin-right:7px;box-shadow:0 0 10px var(--acid)}main{max-width:1440px;margin:auto;padding:0 4vw 70px}.hero{position:relative;padding:74px 0 54px;max-width:930px}.hero:after{content:"BUILD / REVIEW / REFINE";position:absolute;right:-38%;top:92px;writing-mode:vertical-rl;font-size:10px;letter-spacing:.45em;color:#7f8178}.eyebrow{font:700 11px/1 monospace;letter-spacing:.2em}.eyebrow span{background:var(--ink);color:var(--paper);padding:4px 7px;margin-left:7px}.hero h1{font:900 clamp(50px,7vw,105px)/.87 Georgia,serif;letter-spacing:-.065em;margin:24px 0}.hero h1 em{color:var(--signal);font-weight:400}.hero p{max-width:610px;font:20px/1.45 Georgia,serif;color:#50534c}.workbench{display:grid;grid-template-columns:minmax(320px,.78fr) minmax(520px,1.22fr);gap:18px}.brief-card,.floor-card,.output-deck{border:2px solid var(--line);background:#f6f1e5;box-shadow:7px 7px 0 var(--line)}.card-head{min-height:67px;border-bottom:2px solid var(--line);display:flex;align-items:center;gap:13px;padding:13px 16px}.card-head>span,.deck-head span{font:900 30px Georgia;color:var(--signal)}.card-head b,.deck-head b{letter-spacing:.12em}.card-head small{display:block;color:var(--steel);margin-top:3px}.card-head strong{margin-left:auto;font:900 28px Georgia}.brief-card{padding-bottom:16px}.brief-card label{display:block;margin:16px 16px 0;font-size:10px;font-weight:bold;letter-spacing:.12em}.brief-card input,.brief-card textarea{display:block;width:100%;margin-top:7px;border:1.5px solid var(--line);background:#fffdf6;padding:12px;font:15px/1.4 Georgia,serif;color:var(--ink);outline:none}.brief-card input:focus,.brief-card textarea:focus{border-color:var(--signal);box-shadow:3px 3px 0 #f8b09f}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:0}.presence-choice{margin:16px;border:1.5px solid var(--line);padding:12px}.presence-choice legend{font-size:10px;font-weight:bold;letter-spacing:.12em}.presence-options{display:grid;grid-template-columns:1fr 1fr;gap:6px}.presence-options button{border:1px solid var(--line);background:#fffdf6;color:var(--ink);padding:9px;font:700 9px monospace;cursor:pointer}.presence-options button.selected{background:var(--ink);color:var(--paper)}#presence-note{display:block;margin-top:8px;color:var(--steel);font:10px/1.3 Georgia}.brief-card button[type=submit]{margin:20px 16px 0;width:calc(100% - 32px);border:0;background:var(--signal);color:#fff;padding:15px 17px;display:flex;justify-content:space-between;font-weight:900;letter-spacing:.13em;cursor:pointer;box-shadow:4px 4px 0 var(--ink);transition:.2s}.brief-card button[type=submit]:hover{transform:translate(-2px,-2px);box-shadow:6px 6px 0 var(--ink)}.micro{font-size:9px;text-align:center;color:var(--steel);letter-spacing:.08em}.rail{height:8px;background:#d1ccbf;border-bottom:1px solid var(--line)}.rail div{height:100%;width:0;background:var(--signal);transition:width .5s}.stations{padding:10px}.stations article{display:grid;grid-template-columns:58px 1fr auto;gap:15px;align-items:center;padding:13px;border:1px solid transparent;border-bottom-color:#c3bfb3;transition:.35s}.stations article.active{background:#fff8e5;border-color:var(--line);transform:translateX(-5px);box-shadow:5px 5px 0 var(--gold)}.stations article.done{opacity:.7}.portrait{width:52px;height:52px;display:grid;place-items:center;color:white;font:900 28px Georgia;border-radius:50%;box-shadow:inset 0 0 0 3px #ffffff55}.atlas{background:#4a7187}.aria{background:#a64d36}.vera{background:#2b6450}.mason{background:#8e6d32}.stations small{font-size:8px;letter-spacing:.16em;color:var(--steel)}.stations h3{font:900 23px/1 Georgia;margin:3px 0}.stations p{font:13px/1.3 Georgia;margin:0;color:#565950}.stations mark{background:#d7d2c6;padding:5px 7px;font-size:8px;letter-spacing:.1em}.stations .active mark{background:var(--acid)}.stations .done mark{background:var(--ink);color:white}.output-deck{margin-top:70px}.deck-head{display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid var(--line);padding:13px 18px}.deck-head>div{display:flex;align-items:center;gap:12px}.deck-head nav{display:flex;gap:4px}.deck-head button{border:1px solid var(--line);background:transparent;padding:8px 11px;text-transform:uppercase;font:700 9px monospace;cursor:pointer}.deck-head button.active{background:var(--ink);color:white}.tab{display:none;padding:22px}.tab.active{display:block;animation:reveal .4s ease}.agent-poster{background:var(--ink);color:var(--paper);padding:32px;display:flex;justify-content:space-between;align-items:center}.agent-poster small,.evidence-grid small,.handoff small,.concierge-shell aside>small{letter-spacing:.18em;color:var(--acid);font-size:9px}.agent-poster h2{font:900 clamp(32px,5vw,70px)/.95 Georgia;margin:8px 0}.agent-poster p{font:17px Georgia;color:#c6c4bb}.seal{border:2px solid var(--signal);color:var(--signal);border-radius:50%;width:110px;height:110px;display:grid;place-items:center;text-align:center;transform:rotate(7deg);font-size:11px;letter-spacing:.15em}.seal b{font:900 20px Georgia}.spec-grid,.evidence-grid{display:grid;grid-template-columns:1fr 1fr}.spec-grid>div,.evidence-grid>div{padding:22px;border:1px solid var(--line);margin:-1px 0 0 -1px}.spec-grid small,.evidence-grid small{color:var(--signal);font-weight:bold}.spec-grid p,.spec-grid li,.evidence-grid p{font:14px/1.5 Georgia}.concierge-shell{display:grid;grid-template-columns:270px 1fr 260px;min-height:520px;border:1px solid var(--line)}.concierge-shell aside{background:var(--blue);color:white;padding:24px}.concierge-shell aside h2{font:900 30px Georgia}.concierge-shell aside p{font:13px Georgia}.concierge-shell aside button{display:block;width:100%;margin:8px 0;border:1px solid #ffffff88;background:transparent;color:white;padding:9px;text-align:left;font:11px Georgia;cursor:pointer}.avatar-stage{height:190px;margin:14px 0 20px;background:linear-gradient(155deg,#2e4d5d,#8d705b);position:relative;overflow:hidden;display:grid;place-items:center}.avatar-stage:before{content:"";position:absolute;width:180px;height:180px;border:1px solid #ffffff44;border-radius:50%;top:25px}.avatar-head{width:90px;height:118px;position:relative;z-index:1}.avatar-head i{position:absolute;width:72px;height:72px;border-radius:50%;background:#e7c9b0;left:9px;top:0;box-shadow:inset 0 10px 0 #3d2e29}.avatar-head b{position:absolute;width:90px;height:64px;border-radius:48px 48px 0 0;background:#1b2528;bottom:0}.avatar-stage.text-only .avatar-head{display:none}.avatar-stage.stock .avatar-head{filter:grayscale(1)}.avatar-stage span{position:absolute;bottom:8px;font:700 8px monospace;letter-spacing:.12em;background:#111c;padding:5px 7px}.conversation{padding:24px;background:#fffdf6;display:flex;flex-direction:column}.message{max-width:78%;padding:12px 14px;margin:6px 0;font:14px/1.4 Georgia;border-radius:2px}.message.bot{background:#e7e0d1}.message.user{background:var(--acid);align-self:flex-end}.composer{display:flex;margin-top:auto;border-top:1px solid #bbb;padding-top:15px}.composer input{flex:1;padding:11px;border:1px solid var(--line)}.composer button,.handoff button{background:var(--signal);color:white;border:0;padding:10px 13px;font-weight:bold;cursor:pointer}.handoff{background:#e2ddcf;padding:22px}.handoff-field{border-bottom:1px solid #aaa;padding:8px 0}.handoff-field small{color:#686b64}.handoff-field b{display:block;font:13px Georgia;margin-top:3px}.handoff button{width:100%;margin-top:10px}.handoff button.ghost{background:transparent;color:var(--ink);border:1px solid var(--ink)}footer{background:var(--ink);color:#8f9288;padding:22px 4vw;display:flex;justify-content:space-between;font:9px monospace;letter-spacing:.15em}@keyframes reveal{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}@media(max-width:980px){.workbench{grid-template-columns:1fr}.concierge-shell{grid-template-columns:1fr}.hero:after{display:none}}@media(max-width:620px){.masthead{padding:0 18px}.safety{display:none}main{padding:0 18px 50px}.two-col,.spec-grid,.evidence-grid{grid-template-columns:1fr}.deck-head{align-items:flex-start;gap:12px;flex-direction:column}.agent-poster{align-items:flex-start}.seal{width:80px;height:80px}.stations article{grid-template-columns:48px 1fr}.stations mark{grid-column:2}.portrait{width:44px;height:44px}.hero{padding-top:48px}}
"""

    css += """.avatar-stage.has-reference{background:#202723}.avatar-stage.has-reference:before,.avatar-stage.has-reference .avatar-head{display:none}#avatar-reference{display:none;width:100%;height:100%;object-fit:cover;object-position:center 18%}.avatar-stage.has-reference #avatar-reference{display:block}.avatar-stage span{z-index:2}#persona-reference{border-left:3px solid var(--acid);padding-left:9px;color:#fff;font:11px/1.4 Georgia;margin:0 0 14px}#persona-reference:empty{display:none}
"""

    js_data = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    js = """const DATA=__DATA__;
const owner=DATA.owner, bp=DATA.blueprint, inputs=owner.implementation_inputs;
const recovery=Boolean(bp.raw_intake&&bp.raw_intake.recovery_provenance);
const experience=owner.experience_shell||(bp.raw_intake&&bp.raw_intake.experience_shell)||{presence_mode:'TEXT_ONLY',selection_status:'DEFERRED',disclosure:{visible_label:'AI concierge',opening_disclosure:'I am an AI concierge.'}};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
$('#mission-id').textContent=owner.run_id; $('#purpose').value=owner.purpose; $('#client').value=owner.agent_or_client||''; $('#personality').value=owner.role_and_behavior||''; $('#must').value=owner.must_have_capabilities.join(', '); $('#never').value=owner.never_do.join(', ');
$('#agent-name').textContent=bp.identity.agent_name||bp.candidate_id; $('#concierge-name').textContent=bp.identity.agent_name||bp.candidate_id; $('#agent-role').textContent=bp.identity.persona; $('#primary-job').textContent=bp.objectives.primary_job; $('#component').textContent=(bp.components.selected[0]||{}).component_id||'Custom blueprint';
$('#ai-label').textContent=experience.disclosure.visible_label;$('#opening-message').textContent=experience.disclosure.opening_disclosure+' I can answer approved questions and help prepare a request for staff review. What would you like to do?';
const presenceLabels={EXISTING_ANAM:'EXISTING ANAM AVATAR',CREATE_NEW_ANAM:'NEW ANAM AVATAR BRIEF',STOCK_IMAGE:'STOCK IMAGE FALLBACK',TEXT_ONLY:'TEXT-ONLY MODE',UNDECIDED:'PRESENCE NOT SELECTED'};const recommendedAvatar=experience.selection_status==='FACTORY_RECOMMENDED'&&experience.avatar&&experience.avatar.existing_avatar_id;let presenceMode=experience.presence_mode;const referenceImage=$('#avatar-reference');if(DATA.preview&&DATA.preview.portrait)referenceImage.src=DATA.preview.portrait;function renderPresence(){const stage=$('#avatar-stage');const showReference=presenceMode==='EXISTING_ANAM'&&Boolean(DATA.preview&&DATA.preview.portrait);stage.classList.toggle('text-only',presenceMode==='TEXT_ONLY'||presenceMode==='UNDECIDED');stage.classList.toggle('stock',presenceMode==='STOCK_IMAGE');stage.classList.toggle('has-reference',showReference);$('#avatar-mode').textContent=showReference&&recommendedAvatar?(experience.avatar.display_name.toUpperCase()+' · FACTORY RECOMMENDED'):presenceLabels[presenceMode];$$('[data-presence]').forEach(b=>b.classList.toggle('selected',b.dataset.presence===presenceMode));$('#persona-reference').textContent=showReference&&recommendedAvatar?'ANAM stock persona · '+experience.voice.style:'';$('#presence-note').textContent=presenceMode==='EXISTING_ANAM'?(recommendedAvatar?'Factory recommendation: '+experience.avatar.display_name+'. Keep it, choose another ANAM persona, or create a new one.':'Choose from connected ANAM avatars.'):presenceMode==='CREATE_NEW_ANAM'?'The Factory will prepare an ANAM creation brief; provider creation still requires approval.':presenceMode==='STOCK_IMAGE'?'A client-approved stock image will be used until an avatar is connected.':presenceMode==='TEXT_ONLY'?'The agent stays fully usable without a visual avatar.':'Choose now or let the Factory recommend one later.'}$$('[data-presence]').forEach(b=>b.onclick=()=>{presenceMode=b.dataset.presence;renderPresence()});renderPresence();
const fill=(id,items,n=4)=>{const e=$(id);e.textContent='';items.slice(0,n).forEach(x=>{const li=document.createElement('li');li.textContent=typeof x==='string'?x:(x.statement||JSON.stringify(x));e.append(li)})}; fill('#boundaries',bp.boundaries.prohibited_actions);fill('#tests',bp.evaluation_plan.scenarios);
$$('.deck-head button').forEach(b=>b.onclick=()=>{$$('.deck-head button').forEach(x=>x.classList.toggle('active',x===b));$$('.tab').forEach(x=>x.classList.toggle('active',x.id===b.dataset.tab))});
let running=false;$('#mission-form').onsubmit=async e=>{e.preventDefault();if(running)return;running=true;const stations=$$('#stations article');const recovered=['SOURCE','SOURCE','REMEDIATED','BUILT'];for(let i=0;i<stations.length;i++){stations[i].classList.add('active');stations[i].querySelector('mark').textContent='WORKING';$('#floor-status').textContent=recovery?['Loading accepted Atlas intake','Loading accepted Aria blueprint','Applying Vera defect corrections','Running deterministic local build'][i]:['Atlas is locking the intake','Aria is drawing the blueprint','Vera is checking every seam','Mason is assembling the draft'][i];$('#progress').textContent=(i*25+10)+'%';$('#rail-fill').style.width=(i*25+10)+'%';await new Promise(r=>setTimeout(r,650));stations[i].classList.remove('active');stations[i].classList.add('done');stations[i].querySelector('mark').textContent=recovery?recovered[i]:'PASSED'}$('#progress').textContent='100%';$('#rail-fill').style.width='100%';$('#floor-status').textContent=recovery?'Local remediated draft ready for review':'Contained draft ready for review';running=false;$('#summary').scrollIntoView({behavior:'smooth'})};
const messages=$('#messages');function add(text,type){const d=document.createElement('div');d.className='message '+type;d.textContent=text;messages.append(d);d.scrollIntoView({behavior:'smooth'})}inputs.approved_faqs.forEach(f=>{const b=document.createElement('button');b.textContent=f.question;b.onclick=()=>{add(f.question,'user');setTimeout(()=>add(f.answer,'bot'),180)};$('#faq-buttons').append(b)});function send(){const v=$('#chat-input').value.trim();if(!v)return;add(v,'user');$('#chat-input').value='';const hit=inputs.approved_faqs.find(f=>v.toLowerCase().includes(f.question.toLowerCase().split(' ').slice(1,4).join(' ')));setTimeout(()=>add(hit?hit.answer:'I do not have an approved answer for that. I can record it as a known unknown for staff review.','bot'),180)}$('#send-chat').onclick=send;$('#chat-input').onkeydown=e=>{if(e.key==='Enter')send()};
const handoff={request_summary:'Awaiting visitor details',service_category:'Not provided',property_type:'Not provided',service_city:'Not provided',urgency:'Not provided',preferred_contact_window:'No preference',recommended_queue:inputs.handoff_contract.recommended_queue};function renderHandoff(){$('#handoff-fields').textContent='';Object.entries(handoff).forEach(([k,v])=>{const d=document.createElement('div');d.className='handoff-field';const s=document.createElement('small');s.textContent=k.replaceAll('_',' ').toUpperCase();const b=document.createElement('b');b.textContent=v;d.append(s,b);$('#handoff-fields').append(d)})}renderHandoff();$('#copy-handoff').onclick=async()=>{await navigator.clipboard.writeText(JSON.stringify(handoff,null,2));$('#copy-handoff').textContent='COPIED';setTimeout(()=>$('#copy-handoff').textContent='COPY JSON',900)};$('#reset-preview').onclick=()=>{messages.textContent='';$('#chat-input').value=''};
""".replace("__DATA__", js_data)

    (output / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (output / "styles.css").write_text(css, encoding="utf-8", newline="\n")
    (output / "app.js").write_text(js, encoding="utf-8", newline="\n")
    return FILES + ((preview_portrait,) if preview_portrait else ())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-intake", type=Path, required=True)
    parser.add_argument("--blueprint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = generate(args.owner_intake, args.blueprint, args.output)
    print(json.dumps({"status": "SUCCESS", "files": files, "network_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
