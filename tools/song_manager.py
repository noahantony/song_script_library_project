#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, re, subprocess, os, datetime, urllib.parse

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content-repository"
HOST, PORT = "127.0.0.1", int(os.environ.get("LYRICSNEST_MANAGER_PORT", "8765"))

def readj(p): return json.loads(p.read_text(encoding="utf-8"))
def writej(p, d): p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def safe_path(s):
    p = Path(s)
    if not s or p.is_absolute() or ".." in p.parts or "\\" in s: raise ValueError("Invalid repository-relative path.")
    q = (CONTENT / p).resolve()
    if q != CONTENT.resolve() and CONTENT.resolve() not in q.parents: raise ValueError("Path escapes content-repository.")
    return q
def library():
    c = readj(CONTENT / "catalog.json"); entries=[]
    for lang in c.get("languages", []):
        idx = readj(safe_path(lang["index"]))
        for x in idx.get("items", []):
            entries.append({**x, "language":lang["code"], "languageName":lang.get("name",lang["code"]), "indexPath":lang["index"]})
    return c, entries
def git(args, timeout=30):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)

PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LyricsNest Song Manager</title>
<style>
:root{--ink:#242039;--muted:#77738a;--line:#e8e4ef;--violet:#5c43a5}*{box-sizing:border-box}body{margin:0;background:#f7f5fb;color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}header{background:#241d3b;color:white;padding:20px max(18px,calc((100vw - 1200px)/2));display:flex;justify-content:space-between;align-items:center}.brand{display:flex;gap:12px;align-items:center}.nest{font-size:32px}h1{font-size:21px;margin:0}header p{margin:2px 0;color:#d4cce9;font-size:13px}main{max-width:1200px;margin:22px auto;padding:0 18px}.layout{display:grid;grid-template-columns:290px minmax(0,1fr);gap:18px}.panel{background:white;border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 4px 18px #30205408}h2{font-size:17px;margin:0 0 14px}.muted{color:var(--muted);font-size:13px}input,select,textarea{width:100%;font:inherit;border:1px solid #dcd6e8;border-radius:9px;padding:10px;background:white;color:var(--ink)}label{display:block;font-size:13px;font-weight:650;margin:12px 0 5px}textarea{min-height:300px;resize:vertical;font:14px/1.6 ui-monospace,Consolas,monospace}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.row{display:flex;gap:9px;align-items:center}.grow{flex:1;min-width:0}button{border:0;border-radius:9px;padding:10px 13px;background:var(--violet);color:white;font-weight:600;cursor:pointer}button.secondary{background:#eeeaf7;color:#403361}.full{width:100%}.songlist{display:flex;flex-direction:column;gap:5px;max-height:50vh;overflow:auto;margin-top:12px}.song{padding:10px;border:1px solid transparent;border-radius:10px;cursor:pointer;text-align:left;background:transparent;color:var(--ink);width:100%}.song:hover,.song.active{background:#f0ebfa;border-color:#dcd2f2}.song strong{display:block}.song small{color:var(--muted)}.toolbar,.actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.toolbar button{padding:7px 9px;font-size:12px}.editorgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.preview{min-height:300px;max-height:600px;overflow:auto;border:1px solid var(--line);border-radius:10px;padding:14px;background:#fffdfb;overflow-wrap:anywhere}.preview p{margin:0 0 12px}.preview hr{border:0;border-top:1px solid #ddd;margin:18px 0}.notice{padding:11px 13px;border-radius:10px;background:#f0ecf8;margin:12px 0;font-size:13px}.error{background:#fff0f0;color:#9e2736}.success{background:#e9f7ef;color:#176943}.statusbox{font:12px/1.6 ui-monospace,monospace;background:#211c31;color:#eee7ff;padding:12px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}.pill{font-size:12px;background:#f0ecf8;border-radius:99px;padding:4px 8px;color:#5b478b}.hidden{display:none}@media(max-width:850px){.layout,.editorgrid{grid-template-columns:1fr}.songlist{max-height:220px}header{padding:16px}}
</style></head><body><header><div class="brand"><div class="nest">🪺</div><div><h1>LyricsNest Song Manager</h1><p>Local content editor · Markdown + JSON · Git review</p></div></div><span class="pill">LOCAL ONLY</span></header>
<main><div class="layout"><aside class="panel"><h2>Library</h2><input id="search" placeholder="Search title, ID, tags…" oninput="renderList()"><div class="row" style="margin-top:10px"><button class="full" onclick="newItem()">＋ New item</button><button class="secondary" onclick="loadAll()">Refresh</button></div><div id="list" class="songlist"></div><div class="notice">Edits are saved to your local repository. Review Git changes before pushing.</div><h2 style="margin-top:20px">Git status</h2><div id="status" class="statusbox">Checking…</div><div class="actions"><button class="secondary" onclick="refreshStatus()">Refresh status</button><button onclick="showGit()">Review changes</button></div></aside>
<section class="panel"><div class="row"><div class="grow"><h2 id="heading">Add a song or script</h2><div class="muted">Required: language, title, type, ID and content. Metadata is optional.</div></div><span id="mode" class="pill">NEW</span></div><div id="message"></div>
<div class="grid2"><div><label>Language</label><select id="lang"></select></div><div><label>Type</label><select id="type"><option value="song">Song</option><option value="script">Script</option></select></div></div>
<div class="grid2"><div><label>Title *</label><input id="title" placeholder="Song title"></div><div><label>Unique ID *</label><input id="id" placeholder="ta-song-example"></div></div>
<div class="grid2"><div><label>Category</label><input id="category" placeholder="Worship, Motivation…"></div><div><label>Tags (comma separated)</label><input id="tags" placeholder="praise, hope"></div></div>
<div class="grid2"><div><label>Author (optional)</label><input id="author"></div><div><label>Composer (optional)</label><input id="composer"></div></div>
<label>Markdown path *</label><input id="path" placeholder="ta/songs/song-title.md">
<div class="toolbar"><button class="secondary" onclick="wrap('**','**')">Bold</button><button class="secondary" onclick="wrap('*','*')">Italic</button><button class="secondary" onclick="wrap('{{color:#D32F2F|','}}')">Red text</button><button class="secondary" onclick="wrap('{{highlight:#FFF0A6|','}}')">Highlight</button><button class="secondary" onclick="insert('## Verse 1\\n\\n')">Heading</button><button class="secondary" onclick="insert('\\n---\\n\\n')">Divider</button></div>
<div class="editorgrid"><div><label>Lyrics / content (Markdown)</label><textarea id="markdown" placeholder="# Title&#10;&#10;Enter lyrics here…" oninput="preview()"></textarea></div><div><label>Live preview</label><div id="preview" class="preview"></div><p class="muted">Supports headings, paragraphs, lists, bold, italic, custom colors and highlights.</p></div></div>
<div class="actions"><button onclick="save()">Save locally</button><button class="secondary" onclick="newItem()">Reset form</button><button class="secondary" onclick="showGit()">Review Git changes</button></div><div class="notice">Saving writes the Markdown file and updates the language index. catalog.json is the language registry and changes only when languages are added or removed.</div>
</section></div>
<section id="gitpanel" class="panel hidden" style="margin-top:18px"><h2>Review before commit and push</h2><p class="muted">Inspect the diff and status. Git uses your existing local credentials; no token is stored here.</p><div id="diff" class="statusbox">Loading…</div><label>Commit message</label><input id="commitmsg" value="Add or update LyricsNest content"><div class="actions"><button onclick="loadDiff()">Refresh diff</button><button onclick="commitPush()">Commit and push</button><button class="secondary" onclick="gitpanel.classList.add('hidden')">Close</button></div><div id="gitmsg"></div></section></main>
<script>
let catalog={languages:[]},items=[],current=null;
const $=x=>document.getElementById(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url,opt={}){let r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt}),d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d}
function message(s,err=false){$('message').innerHTML=`<div class="notice ${err?'error':'success'}">${esc(s)}</div>`}
async function loadAll(){try{let d=await api('/api/library');catalog=d.catalog;items=d.entries;let old=$('lang').value;$('lang').innerHTML=catalog.languages.map(x=>`<option value="${esc(x.code)}">${esc(x.name)} (${esc(x.code)})</option>`).join('');if(old)$('lang').value=old;renderList();await refreshStatus()}catch(e){message(e.message,true)}}
function renderList(){let q=$('search').value.toLowerCase(),a=items.filter(x=>(x.title+' '+x.id+' '+x.language+' '+(x.tags||[]).join(' ')).toLowerCase().includes(q));$('list').innerHTML=a.map(x=>`<button class="song ${current===x.path?'active':''}" onclick="edit('${esc(x.path)}')"><strong>${esc(x.title)}</strong><small>${esc(x.language)} · ${esc(x.type)} · ${esc(x.id)}</small></button>`).join('')||'<p class="muted">No matching items.</p>'}
function slug(s){return s.toLowerCase().normalize('NFKD').replace(/[^\w-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'').slice(0,80)||'untitled'}
function defaults(){let lang=$('lang').value,type=$('type').value,title=$('title').value;$('path').value=`${lang}/${type==='script'?'scripts':'songs'}/${slug(title)}.md`;if(!$('id').dataset.touched)$('id').value=`${lang}-${type}-${slug(title)}`.slice(0,120)}
$('title').addEventListener('input',()=>{if(!current)defaults()});$('lang').addEventListener('change',()=>{if(!current)defaults()});$('type').addEventListener('change',()=>{if(!current)defaults()});$('id').addEventListener('input',()=>{$('id').dataset.touched='1'});
function newItem(){current=null;$('heading').textContent='Add a song or script';$('mode').textContent='NEW';['title','id','category','tags','author','composer','path','markdown'].forEach(x=>$(x).value='');$('id').dataset.touched='';$('type').value='song';defaults();preview();renderList();$('message').innerHTML=''}
async function edit(path){try{let d=await api('/api/item?path='+encodeURIComponent(path)),x=d.item;current=path;$('heading').textContent='Edit existing item';$('mode').textContent='EDIT';$('lang').value=x.language;$('type').value=x.type;$('title').value=x.title;$('id').value=x.id;$('id').dataset.touched='1';$('category').value=x.category||'';$('tags').value=(x.tags||[]).join(', ');$('author').value=x.author||'';$('composer').value=x.composer||'';$('path').value=x.path;$('markdown').value=d.markdown;preview();renderList();$('message').innerHTML=''}catch(e){message(e.message,true)}}
function wrap(a,b){let t=$('markdown'),s=t.selectionStart,e=t.selectionEnd,v=t.value;t.value=v.slice(0,s)+a+v.slice(s,e)+b+v.slice(e);t.focus();t.selectionStart=s+a.length;t.selectionEnd=e+a.length;preview()}
function insert(s){let t=$('markdown'),p=t.selectionStart;t.value=t.value.slice(0,p)+s+t.value.slice(p);t.focus();preview()}
function inline(s){return esc(s).replace(/\{\{color:(#[0-9a-fA-F]{6})\|([\s\S]*?)\}\}/g,'<span style="color:$1">$2</span>').replace(/\{\{highlight:(#[0-9a-fA-F]{6})\|([\s\S]*?)\}\}/g,'<span style="background:$1;padding:1px 3px;border-radius:3px">$2</span>').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>').replace(/`([^`]+)`/g,'<code>$1</code>')}
function renderMd(s){let out=[],p=[],ul=false;const flush=()=>{if(p.length){out.push('<p>'+inline(p.join('\\n')).replace(/\\n/g,'<br>')+'</p>');p=[]}},close=()=>{if(ul){out.push('</ul>');ul=false}};for(let l of s.split(/\\r?\\n/)){if(!l.trim()){flush();close();continue}let h=l.match(/^(#{1,3})\\s+(.+)$/);if(h){flush();close();out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);continue}if(/^---+\\s*$/.test(l)){flush();close();out.push('<hr>');continue}let li=l.match(/^\\s*[-*]\\s+(.+)$/);if(li){flush();if(!ul){out.push('<ul>');ul=true}out.push('<li>'+inline(li[1])+'</li>');continue}close();p.push(l)}flush();close();return out.join('')||'<span class="muted">Preview appears here…</span>'}
function preview(){$('preview').innerHTML=renderMd($('markdown').value)}
async function save(){try{let d={language:$('lang').value,type:$('type').value,title:$('title').value.trim(),id:$('id').value.trim(),category:$('category').value.trim(),tags:$('tags').value.split(',').map(x=>x.trim()).filter(Boolean),author:$('author').value.trim(),composer:$('composer').value.trim(),path:$('path').value.trim(),markdown:$('markdown').value,originalPath:current};let r=await api('/api/save',{method:'POST',body:JSON.stringify(d)});current=r.path;message('Saved '+r.path+' and updated the language index.');await loadAll();await edit(r.path)}catch(e){message(e.message,true)}}
async function refreshStatus(){try{let d=await api('/api/git/status');$('status').textContent=d.status||'Working tree clean'}catch(e){$('status').textContent=e.message}}
async function showGit(){$('gitpanel').classList.remove('hidden');await loadDiff();$('gitpanel').scrollIntoView({behavior:'smooth'})}
async function loadDiff(){try{let d=await api('/api/git/diff');$('diff').textContent=d.text||'No changes';$('gitmsg').innerHTML='';await refreshStatus()}catch(e){$('diff').textContent=e.message}}
async function commitPush(){if(!confirm('Stage ALL repository changes, commit, and push the current branch? Review status and diff first.'))return;try{let d=await api('/api/git/commit-push',{method:'POST',body:JSON.stringify({message:$('commitmsg').value})});$('gitmsg').innerHTML='<div class="notice success">'+esc(d.output)+'</div>';await loadDiff()}catch(e){$('gitmsg').innerHTML='<div class="notice error">'+esc(e.message)+'</div>'}}
loadAll();preview();
</script></body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print("%s - %s" % (self.address_string(), fmt % args))
    def sendj(self, obj, code=200):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b)
    def body(self):
        n=int(self.headers.get("Content-Length","0"))
        if n>5_000_000: raise ValueError("Request too large.")
        return json.loads(self.rfile.read(n).decode("utf-8"))
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        try:
            if u.path=="/":
                b=PAGE.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
            if u.path=="/api/library":
                c,e=library();return self.sendj({"catalog":c,"entries":e})
            if u.path=="/api/item":
                p=urllib.parse.parse_qs(u.query).get("path",[""])[0];f=safe_path(p);_,es=library()
                item=next((x for x in es if x["path"]==p),None)
                if not item:return self.sendj({"error":"Item not found in a language index."},404)
                return self.sendj({"item":item,"markdown":f.read_text(encoding="utf-8")})
            if u.path=="/api/git/status":
                p=git(["status","--short"]);return self.sendj({"status":p.stdout.strip() if p.returncode==0 else p.stderr.strip()})
            if u.path=="/api/git/diff":
                p=git(["diff","--","content-repository"]);s=git(["status","--short"])
                return self.sendj({"text":(p.stdout or "(No tracked diff yet.)")+"\\n\\n--- git status --short ---\\n"+s.stdout})
            return self.sendj({"error":"Not found"},404)
        except Exception as e:return self.sendj({"error":str(e)},400)
    def do_POST(self):
        try:
            if self.path=="/api/save":
                d=self.body();lang=str(d.get("language","")).strip();title=str(d.get("title","")).strip();ident=str(d.get("id","")).strip();typ=d.get("type");p=str(d.get("path","")).strip();md=d.get("markdown","");old=d.get("originalPath")
                if not all([lang,title,ident,typ,p]) or typ not in ("song","script") or not isinstance(md,str) or not md.strip():raise ValueError("Language, title, ID, type, path and content are required.")
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,119}",ident):raise ValueError("ID must be 2–120 letters, numbers, underscores or hyphens.")
                cat=readj(CONTENT/"catalog.json");l=next((x for x in cat.get("languages",[]) if x["code"]==lang),None)
                if not l:raise ValueError("Unknown language. Add it to catalog.json and create its index first.")
                prefix=f"{lang}/{'songs' if typ=='song' else 'scripts'}/"
                if not p.startswith(prefix) or not p.endswith(".md"):raise ValueError(f"Path must start with {prefix} and end in .md.")
                target=safe_path(p);idxpath=safe_path(l["index"]);idx=readj(idxpath);_,es=library()
                for x in es:
                    if x["id"]==ident and x["path"]!=old:raise ValueError(f"Duplicate ID '{ident}' already used by {x['path']}.")
                    if x["path"]==p and x["path"]!=old:raise ValueError(f"Duplicate indexed path: {p}")
                if target.exists() and p!=old:raise ValueError("File already exists. Choose a new filename or edit the existing item.")
                for m in re.finditer(r"\{\{(?:color|highlight):([^|]+)\|",md):
                    if not re.fullmatch(r"#[0-9a-fA-F]{6}",m.group(1).strip()):raise ValueError("Colors must be six-digit hex values such as #D32F2F.")
                item={"id":ident,"title":title,"type":typ,"path":p,"updatedAt":datetime.date.today().isoformat()}
                if d.get("category"):item["category"]=str(d["category"]).strip()
                tags=d.get("tags") or []
                if tags:item["tags"]=list(dict.fromkeys(str(t).strip() for t in tags if str(t).strip()))
                if d.get("author"):item["author"]=str(d["author"]).strip()
                if d.get("composer"):item["composer"]=str(d["composer"]).strip()
                if old and old!=p:
                    oldfile=safe_path(old)
                    if oldfile.exists():oldfile.unlink()
                idx["items"]=[x for x in idx.get("items",[]) if x.get("path") not in (old,p)]
                idx["items"].append(item);idx["items"].sort(key=lambda x:(x.get("title","").casefold(),x.get("id","")))
                target.parent.mkdir(parents=True,exist_ok=True);target.write_text(md.rstrip()+"\\n",encoding="utf-8");writej(idxpath,idx)
                return self.sendj({"ok":True,"path":p,"item":item})
            if self.path=="/api/git/commit-push":
                msg=str(self.body().get("message","")).strip()
                if not msg:raise ValueError("Enter a commit message.")
                a=git(["add","-A"],timeout=30)
                if a.returncode:raise ValueError(a.stderr.strip() or "git add failed")
                d=git(["diff","--cached","--quiet"])
                if d.returncode==0:raise ValueError("There are no staged changes to commit.")
                c=git(["commit","-m",msg],timeout=45)
                if c.returncode:raise ValueError(c.stderr.strip() or c.stdout.strip() or "Commit failed.")
                p=git(["push"],timeout=90)
                if p.returncode:raise ValueError("Commit created locally, but push failed:\\n"+(p.stderr.strip() or p.stdout.strip()))
                return self.sendj({"ok":True,"output":(c.stdout+"\\n"+p.stdout).strip() or "Committed and pushed."})
            return self.sendj({"error":"Not found"},404)
        except subprocess.TimeoutExpired:return self.sendj({"error":"Git command timed out. Check network/repository and retry."},500)
        except Exception as e:return self.sendj({"error":str(e)},400)

if __name__=="__main__":
    if not (CONTENT/"catalog.json").exists():raise SystemExit("content-repository/catalog.json not found.")
    print(f"LyricsNest Song Manager running at http://{HOST}:{PORT}")
    print("Local-only server. Press Ctrl+C to stop.")
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
