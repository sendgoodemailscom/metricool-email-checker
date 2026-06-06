import re
import os
import base64
import subprocess
import tempfile
from html import escape as html_escape
from urllib.parse import quote as url_quote

import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup

# ── Page config ───────────────────────────────────────────────────────────────

ISOTYPE_URL = "https://raw.githubusercontent.com/sendgoodemailscom/metricool-email-checker/main/Isotype_Dark_squared.png"

st.set_page_config(
    page_title="Metricool Email Checker",
    page_icon=ISOTYPE_URL,
    layout="wide",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', Arial, sans-serif; }

  .mc-header { display:flex; align-items:center; gap:18px; padding:20px 24px;
               background:#2d1a29; border-radius:16px; margin-bottom:4px; }
  .mc-logo   { height:52px; width:52px; border-radius:12px; flex:none;
               background:#e7ff56; padding:6px; box-sizing:border-box; }
  .mc-title  { font-size:1.7rem; font-weight:700; color:#e7ff56; margin:0; line-height:1.1; }
  .mc-sub    { font-size:0.92rem; color:#cfc3cc; margin:4px 0 0; }

  .mc-intro  { background:#f4f1f5; border:1px solid #e8d9e4;
               border-radius:12px; padding:16px 20px; margin:6px 0 4px; color:#2d1a29;
               font-size:0.96rem; line-height:1.5; }
  .mc-intro b { color:#2d1a29; }

  .score-box  { padding:14px 20px; border-radius:12px; margin-bottom:6px; font-family:inherit; }
  .score-pass { background:#d0e9d7; }
  .score-warn { background:#fff3ed; }
  .score-fail { background:#ffeaea; }

  div[data-testid="stExpander"] { border:1px solid #e8e8e8; border-radius:12px; margin-bottom:6px; }
  .stButton>button { font-family:'Plus Jakarta Sans',Arial,sans-serif; font-weight:600; border-radius:10px; }
  .stButton>button[kind="primary"] { background:#e7ff56; color:#2d1a29; border:2px solid #2d1a29; }
  .stButton>button[kind="primary"]:hover,
  .stButton>button[kind="primary"]:focus,
  .stButton>button[kind="primary"]:active { background:#2d1a29; color:#e7ff56; border:2px solid #2d1a29; }
  .stButton>button[kind="primary"]:hover * { color:#e7ff56; }

  code { background:#f4f1f5; color:#2d1a29; border-radius:4px; padding:1px 5px; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────

GMAIL_LIMIT = 102_400

BRAND_COLORS = {
    "Yellow":       "#e7ff56",
    "Deep Purple":  "#2d1a29",
    "Pink":         "#f87fdd",
    "Green":        "#50a76a",
    "Light Green":  "#d0e9d7",
    "Orange":       "#fb5124",
    "Light Orange": "#ffc3a1",
    "Blue":         "#596cf2",
    "Light Blue":   "#d5f0fe",
    "Stone/Grey":   "#85b1bd",
}
HEX_TO_NAME = {v: k for k, v in BRAND_COLORS.items()}
ALLOWED_PALETTE = {v.lower() for v in BRAND_COLORS.values()}  # only these hexes are allowed anywhere
# White is tolerated (used widely as a background); black is NOT — our black is Deep Purple.
PALETTE_TOLERATED = {"#ffffff"}

COMPATIBLE = {
    "Deep Purple":  {"Deep Purple","Yellow","Pink","Green","Light Green","Orange","Light Orange","Blue","Light Blue","Stone/Grey"},
    "Yellow":       {"Deep Purple","Yellow","Pink","Green","Light Green","Orange","Light Orange","Blue","Light Blue","Stone/Grey"},
    "Pink":         {"Deep Purple","Yellow","Pink"},
    "Blue":         {"Deep Purple","Yellow","Blue","Light Blue"},
    "Light Blue":   {"Deep Purple","Yellow","Blue","Light Blue"},
    "Orange":       {"Deep Purple","Yellow","Orange","Light Orange"},
    "Light Orange": {"Deep Purple","Yellow","Orange","Light Orange"},
    "Green":        {"Deep Purple","Yellow","Green","Light Green"},
    "Light Green":  {"Deep Purple","Yellow","Green","Light Green"},
    "Stone/Grey":   {"Deep Purple","Yellow","Stone/Grey"},
}

NOISE_SRCS   = ["spacer","ratio","getbee","1x1","video_ratio"]
SOCIAL_LINKS = ["instagram.com","twitter.com","linkedin.com","facebook.com","tiktok.com",
                "pinterest.com","threads.net","bsky.app","youtube.com"]
SKIP_UTM     = ["unsubscribe","mailto:","tally.so","docs.google","politica-privacidad","#"]
UTM_REQUIRED = ["utm_source","utm_medium","utm_campaign"]
ALLOWED_TEXT_COLORS = {"#2d1a29","#ffffff","#fff","#1a1a1a","#596cf2",
                       "#00a4ce","#50a76a","#d5f0fe","#2d1a2a"}

# ── Optimizer ─────────────────────────────────────────────────────────────────

def local_minify(html):
    html = re.sub(r"<!--(?!\[if).*?-->","",html,flags=re.DOTALL)
    html = re.sub(r">\s+<","><",html)
    html = re.sub(r"\s{2,}"," ",html)
    html = re.sub(r'\s*=\s*"','="',html)
    html = "".join(l.strip() for l in html.splitlines())
    html = re.sub(r'="([a-zA-Z0-9_:;.#%,\-]+)"',r"=\1",html)
    return html

def toptal_minify(html):
    with tempfile.NamedTemporaryFile(mode="w",suffix=".html",encoding="utf-8",delete=False) as f:
        f.write(html); tmp=f.name
    try:
        r=subprocess.run(
            ["curl","-s","-X","POST","https://www.toptal.com/developers/html-minifier/api/raw",
             "-H","Content-Type: application/x-www-form-urlencoded","-A","Mozilla/5.0",
             "--data-urlencode",f"input@{tmp}",
             "--data","remove_comments=1&collapse_whitespace=1&remove_redundant_attributes=1&remove_empty_attributes=1"],
            capture_output=True,text=True,timeout=30)
        if r.returncode==0 and r.stdout.strip().startswith("<"):
            return r.stdout
    except Exception:
        pass
    finally:
        os.unlink(tmp)
    return local_minify(html)

def cleanup(html):
    html=re.sub(r"\s*<link[^>]+googleapis[^>]+>","",html)
    for pat in [r"<!--\[if mso\]>\s*<xml>.*?</xml>\s*<!\[endif\]-->",
                r"<!--\[if mso \]><style>.*?</style>\s*<!\[endif\]-->",
                r"<!--\[if mso\]>\s*<v:roundrect.*?<!\[endif\]-->",
                r"<!--\[if vml\]>.*?<!\[endif\]-->",
                r"<!--\[if \(mso\)\|\(IE\)\]>.*?<!\[endif\]-->"]:
        html=re.sub(pat,"",html,flags=re.DOTALL)
    html=html.replace("<!--[if !vml]><!-->","")
    html=html.replace(' role="presentation"',"").replace(" role=presentation","")
    html=re.sub(r"mso-table-lspace:\s*0pt;\s*mso-table-rspace:\s*0pt;\s*","",html)
    html=html.replace(" style=mso-table-lspace:0pt;mso-table-rspace:0pt>",">")
    html=re.sub(r"\s+style=mso-table-lspace:0pt;mso-table-rspace:0pt\b","",html)
    html=re.sub(r";?\s*mso-line-height-alt:[^;>\"']+","",html)
    for pat in [r'<span style="word-break:break-word;">(.*?)</span>',
                r'<span style="word-break: break-word;">(.*?)</span>']:
        html=re.sub(pat,r"\1",html,flags=re.DOTALL)
    html=re.sub(r";?\s*word-break:\s*break-word","",html)
    html=re.sub(r";?\s*box-sizing:\s*\w[\w-]*(?=[;>\"'\s])","",html)
    html=html.replace("<tbody>","").replace("</tbody>","")
    for s in ["border-radius: 0;","border-radius:0;","border-radius:0 0 0 0;",
              "font-weight: 400;","font-weight:400;","background-size: auto;",
              "background-size:auto;","background-image: none;","background-position: top left;",
              "letter-spacing: normal;","letter-spacing:normal;","letter-spacing:0;",
              "mso-border-alt: none;","mso-border-alt:none;","direction:ltr;","direction: ltr;",
              "margin-top:0;margin-bottom:0;","background-image:url('');","background-repeat: no-repeat;"]:
        html=html.replace(s,"")
    html=html.replace(' height="auto"',"").replace(" height=auto","")
    html=re.sub(r'\s+border="0"',"",html)
    html=re.sub(r'\s+cellpadding="0"\s+cellspacing="0"',"",html)
    html=re.sub(r";?\s*min-width:\s*\d+px(?=[;>\"'\s])","",html)
    for a in [r'\s+align="center"',r'\s+align="left"',r'\s+valign="middle"',r"\s+valign=middle"]:
        html=re.sub(a,"",html)
    html=re.sub(r"(<td[^>]*)\s+width=100%",r"\1",html)
    html=re.sub(r'(<td[^>]*)\s+width="100%"',r"\1",html)
    html=html.replace(";text-align:left","").replace("text-align:left;","")
    html=html.replace(";vertical-align:top","").replace("vertical-align:top;","")
    for o,n in [("font-family:Arial,'Helvetica Neue',Helvetica,sans-serif","font-family:Arial,sans-serif"),
                ("font-family: Arial, 'Helvetica Neue', Helvetica, sans-serif","font-family:Arial,sans-serif"),
                ("font-family: Arial, sans-serif","font-family:Arial,sans-serif"),
                ("Nunito, Arial, Helvetica Neue, Helvetica, sans-serif","Arial,sans-serif"),
                ("Nunito,Arial,Helvetica Neue,Helvetica,sans-serif","Arial,sans-serif")]:
        html=html.replace(o,n)
    html=re.sub(r'\s+style=""',"",html)
    return html

def optimize_html(html):
    ok=len(html.encode())/1024
    html=toptal_minify(html)
    html=cleanup(html)
    return html,ok,len(html.encode())/1024


# ── Checks ────────────────────────────────────────────────────────────────────

def is_footer_link(a_tag):
    """Check if link is inside footer area."""
    for parent in a_tag.parents:
        cls = " ".join(parent.get("class", []))
        style = parent.get("style", "")
        if "footer" in cls.lower() or "#2d1a29" in style:
            return True
    return False

def _bg_color(tag):
    """Background-color hex declared on this element, if any."""
    if not hasattr(tag, "get"): return None
    m = re.search(r'background-color:\s*(#[0-9a-fA-F]{3,6})', tag.get("style",""))
    return m.group(1).lower() if m else None

def _text_color(tag):
    """Text color hex declared on this element, if any."""
    if not hasattr(tag, "get"): return None
    m = re.search(r'(?<![background-])color:\s*(#[0-9a-fA-F]{3,6})', tag.get("style",""))
    return m.group(1).lower() if m else None

def _border_color(tag):
    """First border color hex declared on this element, if any."""
    if not hasattr(tag, "get"): return None
    m = re.search(r'border[a-z-]*:\s*[^;]*?(#[0-9a-fA-F]{3,6})', tag.get("style",""))
    return m.group(1).lower() if m else None

def _norm_hex(h):
    """Normalize a hex color to lowercase 6-digit form (#abc -> #aabbcc)."""
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c*2 for c in h[1:])
    return h

def _ancestor_bg(tag):
    """Nearest ancestor's background-color hex — the surface this element sits on."""
    for parent in tag.parents:
        bg = _bg_color(parent)
        if bg: return bg
    return None

def _effective_text_color(node):
    """The text color actually applied to this node: its own, else the nearest
    ancestor that sets one. Avoids flagging container colors that get overridden."""
    el = node
    while el is not None and hasattr(el, "get"):
        c = _text_color(el)
        if c: return c, el
        el = el.parent
    return None, None

def run_checks(html):
    soup = BeautifulSoup(html, "html.parser")
    r = {}

    # Size
    size = len(html.encode())
    r["size"] = {"kb": size/1024, "ok": size <= GMAIL_LIMIT, "over": max(0, size-GMAIL_LIMIT)}

    # Preheader
    ph = soup.find(class_="preheader")
    ph_text = ph.get_text(strip=True) if ph else ""
    r["preheader"] = {"ok": bool(ph_text), "text": ph_text}

    # Unsubscribe
    r["unsubscribe"] = {"ok": "{unsubscribe_text}" in html}

    # Images alt text
    missing_alt = []
    for img in soup.find_all("img"):
        if img.get("alt","").strip(): continue
        src = img.get("src","").lower()
        if any(n in src for n in NOISE_SRCS): continue
        missing_alt.append({"src": img.get("src","(no src)")[:80],
                             "context": img.find_parent("td", class_=True) and
                                        img.find_parent("td",class_=True).get("class","")})
    r["alt_text"] = {"ok": not missing_alt, "missing": missing_alt}

    # Linked images
    linked_logo = [a.get("href","")[:80] for a in soup.find_all("a")
                   if a.find("img") and any(k in a.find("img").get("src","").lower()
                   for k in ["logo","header","banner","vector"])]
    r["linked_images"] = {"ok": not linked_logo, "flagged": linked_logo}

    # UTMs — only metricool.com links, not footer, not PDFs/images
    missing_utm = []
    skip_exts = [".pdf",".jpg",".jpeg",".png",".gif",".webp",".svg",".zip"]
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"): continue
        if "metricool.com" not in href: continue           # only check metricool.com
        if any(s in href for s in SKIP_UTM): continue      # skip utility links
        if any(href.lower().endswith(e) for e in skip_exts): continue  # skip files
        if is_footer_link(a): continue                     # skip footer
        if not all(p in href for p in UTM_REQUIRED):
            text = a.get_text(strip=True)[:40] or href[:60]
            missing_utm.append({"href": href[:90], "text": text})
    r["utm"] = {"ok": not missing_utm, "missing": missing_utm}

    # Videos
    bad_vid = []
    for a in soup.find_all("a", class_="video-preview"):
        href = a.get("href","")
        if href and "youtube" not in href and "youtu.be" not in href:
            bad_vid.append(href[:80])
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"]
        if "youtube" not in src and "youtu.be" not in src:
            bad_vid.append(src[:80])
    r["videos"] = {"ok": not bad_vid, "flagged": bad_vid}

    # Text styling — check the color that ACTUALLY renders on each piece of text
    # (its nearest color-defining ancestor), so a container color that gets
    # overridden by inner elements is not mis-reported as the text color.
    unique_issues, seen_issues = [], set()
    for txt in soup.find_all(string=True):
        s = txt.strip()
        if len(s) <= 3: continue
        c, _decl = _effective_text_color(txt.parent)
        if c and c not in ALLOWED_TEXT_COLORS:
            key = (c, s[:20])
            if key in seen_issues: continue
            seen_issues.add(key)
            unique_issues.append({"color": c, "text": s[:60], "tag": getattr(txt.parent, "name", "")})
    has_arial = "arial" in " ".join(t.get("style","") for t in soup.find_all(True)).lower()
    r["text_style"] = {"ok": has_arial and not unique_issues,
                       "has_arial": has_arial, "issues": unique_issues[:10]}

    # Button styles
    btn_issues = []
    for btn in soup.find_all(class_="button"):
        s = btn.get("style","").replace(" ","")
        t = btn.get_text(strip=True)
        if len(t) > 3 and t != t.upper():
            btn_issues.append(f"Not uppercase: '{t[:40]}'")
        if not any(f"border-radius:{x}px" in s for x in ["14","16"]):
            btn_issues.append(f"Border-radius not 14/16: '{t[:30]}'")
    r["buttons"] = {"ok": not btn_issues, "issues": list(dict.fromkeys(btn_issues))}

    # Color combinations — only check colors that actually touch, and respect
    # borders as separators:
    #   (a) text color vs the background it renders on (readability), and
    #   (b) a colored block vs whatever is directly behind it — BUT if the block
    #       has a border, that border is the visual separator, so we compare each
    #       background against the border instead of against each other.
    # Distant, unrelated sections are NOT compared against each other.
    found_hex = {c.lower() for c in re.findall(r'background-color:\s*(#[0-9a-fA-F]{3,6})', html)}
    named = [HEX_TO_NAME[c] for c in found_hex if c in HEX_TO_NAME]

    conflicts, seen = [], set()

    def _flag(hex_a, hex_b, text):
        na, nb = HEX_TO_NAME.get(hex_a), HEX_TO_NAME.get(hex_b)
        if not na or not nb or na == nb: return
        if nb in COMPATIBLE.get(na, set()): return   # compatible pair → fine
        pair = tuple(sorted([na, nb]))
        if pair in seen: return
        seen.add(pair)
        conflicts.append({"c1": na, "c2": nb, "context": [text] if text else []})

    for tag in soup.find_all(True):
        ctx = tag.get_text(strip=True)[:40]
        # (a) text color vs the background it renders on
        tc = _text_color(tag)
        if tc:
            bg = _bg_color(tag) or _ancestor_bg(tag)
            if bg:
                _flag(tc, bg, ctx)
        # (b) this element's background vs the surface behind it
        own_bg = _bg_color(tag)
        if own_bg:
            border = _border_color(tag)
            parent_bg = _ancestor_bg(tag)
            if border:
                # border separates the two surfaces — check each side against it
                _flag(own_bg, border, ctx)
                if parent_bg:
                    _flag(border, parent_bg, ctx)
            elif parent_bg:
                # backgrounds touch directly — compare them to each other
                _flag(own_bg, parent_bg, ctx)

    r["colors"] = {"ok": not conflicts, "found": named, "conflicts": conflicts}

    # Off-palette colors — any hex used (text, background, or border) that is not
    # one of the 10 allowed brand colors gets a warning. White is tolerated.
    palette_issues, seen_pal = [], set()
    for tag in soup.find_all(True):
        style = tag.get("style","")
        for raw in re.findall(r'#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}\b', style):
            hx = _norm_hex(raw)
            if hx in ALLOWED_PALETTE or hx in PALETTE_TOLERATED or hx in seen_pal: continue
            seen_pal.add(hx)
            ctx = tag.get_text(strip=True)[:40]
            palette_issues.append({"hex": hx, "context": ctx})
    r["palette"] = {"ok": not palette_issues, "off": palette_issues}

    return r


# ── Preview annotator ─────────────────────────────────────────────────────────

PREVIEW_TYPES = {
    "alt":  ("#fb5124", "Missing alt text"),
    "utm":  ("#2d6cdf", "Missing UTM params"),
    "text": ("#d6336c", "Off-brand text color"),
}

def build_preview(html, checks):
    """Two-pane preview: annotated email on the left, an error list on the right.
    Hovering a list item highlights the matching spot in the email and draws a
    connector line between them."""
    soup = BeautifulSoup(html, "html.parser")

    errors = []
    counter = [0]

    def mark(el, etype, detail):
        counter[0] += 1
        mid = f"mc{counter[0]}"
        el["data-mcid"] = mid
        color = PREVIEW_TYPES[etype][0]
        el["style"] = el.get("style","") + f";outline:2px solid {color};outline-offset:1px;"
        errors.append({"id": mid, "color": color,
                       "title": PREVIEW_TYPES[etype][1], "detail": detail})

    # Images missing alt
    for img in soup.find_all("img"):
        if img.get("alt","").strip(): continue
        src = img.get("src","").lower()
        if any(n in src for n in NOISE_SRCS): continue
        mark(img, "alt", img.get("src","(no src)")[:90])

    # Links missing UTMs
    skip_exts = [".pdf",".jpg",".jpeg",".png",".gif",".webp",".svg"]
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"): continue
        if "metricool.com" not in href: continue
        if any(s in href for s in SKIP_UTM): continue
        if any(href.lower().endswith(e) for e in skip_exts): continue
        if is_footer_link(a): continue
        if not all(p in href for p in UTM_REQUIRED):
            mark(a, "utm", (a.get_text(strip=True)[:50] or href[:60]))

    # Off-brand text colors — mark the element that actually renders the text
    # in an off-brand color (effective color), not overridden containers.
    seen_text = set()
    for txt in soup.find_all(string=True):
        s = txt.strip()
        if len(s) <= 3: continue
        c, decl = _effective_text_color(txt.parent)
        if c and c not in ALLOWED_TEXT_COLORS and decl is not None and not decl.has_attr("data-mcid"):
            if (c, s[:20]) in seen_text: continue
            seen_text.add((c, s[:20]))
            mark(decl, "text", f"{c} — {s[:40]}")

    # Route images through a proxy so hotlink-protected sources still render in
    # the preview (metricool.com blocks direct hotlinking). Display-only.
    for img in soup.find_all("img"):
        src = img.get("src","")
        if src.startswith("http"):
            img["src"] = "https://images.weserv.nl/?url=" + url_quote(re.sub(r"^https?://", "", src), safe="")

    body = soup.find("body")
    email_inner = body.decode_contents() if body else str(soup)

    if errors:
        head = f"{len(errors)} issue(s) — hover to locate"
        items = "".join(
            '<div class="mc-item" data-target="%s">'
            '<span class="mc-dot" style="background:%s"></span>'
            '<div class="mc-it-txt"><b>%s</b><br><span class="mc-it-detail">%s</span></div>'
            '</div>' % (e["id"], e["color"], e["title"], html_escape(e["detail"]))
            for e in errors
        )
    else:
        head = "All clear"
        items = '<div class="mc-empty">✅ No visual issues found in the preview.</div>'

    css = """
    #mc-wrap { position:relative; display:flex; font-family:Arial,sans-serif;
               height:840px; border:1px solid #e8e8e8; border-radius:10px; overflow:hidden; }
    #mc-email { flex:1; overflow:auto; background:#fff; }
    #mc-list { width:300px; flex:none; overflow:auto; border-left:1px solid #e8e8e8;
               background:#faf9fb; padding:10px; }
    #mc-list-head { font-size:12px; font-weight:700; color:#2d1a29; margin-bottom:8px; }
    .mc-item { display:flex; gap:8px; align-items:flex-start; padding:8px; border-radius:8px;
               cursor:pointer; margin-bottom:6px; border:1px solid #ececec; background:#fff; }
    .mc-item:hover { background:#2d1a29; border-color:#2d1a29; }
    .mc-item:hover .mc-it-txt, .mc-item:hover .mc-it-detail { color:#fff; }
    .mc-dot { width:10px; height:10px; border-radius:50%; flex:none; margin-top:3px; }
    .mc-it-txt { font-size:12px; line-height:1.35; color:#2d1a29; }
    .mc-it-detail { color:#8a8a8a; font-size:11px; word-break:break-all; }
    .mc-empty { font-size:13px; color:#50a76a; padding:8px; }
    #mc-svg { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:50; }
    .mc-hl { box-shadow:0 0 0 3px rgba(45,26,41,.9), 0 0 0 7px rgba(231,255,86,.65) !important; }
    """

    js = """
    (function(){
      var wrap=document.getElementById('mc-wrap');
      var email=document.getElementById('mc-email');
      var svg=document.getElementById('mc-svg');
      var items=document.querySelectorAll('.mc-item');
      var current=null;
      function clearLine(){ svg.innerHTML=''; }
      function target(it){ return email.querySelector('[data-mcid="'+it.getAttribute('data-target')+'"]'); }
      function drawLine(it,t){
        var w=wrap.getBoundingClientRect(), a=it.getBoundingClientRect(), b=t.getBoundingClientRect(), e=email.getBoundingClientRect();
        var x1=a.left-w.left, y1=a.top-w.top+a.height/2;
        var x2=b.right-w.left, y2=b.top-w.top+b.height/2;
        var top=e.top-w.top, bot=e.bottom-w.top;
        if(y2<top)y2=top; if(y2>bot)y2=bot;
        svg.innerHTML='<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="#2d1a29" stroke-width="1"/>'
                     +'<circle cx="'+x2+'" cy="'+y2+'" r="3.5" fill="#2d1a29"/>'
                     +'<circle cx="'+x1+'" cy="'+y1+'" r="3.5" fill="#2d1a29"/>';
      }
      function deactivate(){ if(!current)return; var t=target(current); if(t)t.classList.remove('mc-hl'); clearLine(); current=null; }
      function activate(it){
        deactivate(); current=it;
        var t=target(it); if(!t)return;
        t.classList.add('mc-hl');
        t.scrollIntoView({block:'center'});
        drawLine(it,t);
        setTimeout(function(){ if(current===it) drawLine(it,t); }, 60);
      }
      items.forEach(function(it){ it.addEventListener('mouseenter', function(){ activate(it); }); });
      document.getElementById('mc-list').addEventListener('mouseleave', deactivate);
      email.addEventListener('scroll', function(){ if(current){ var t=target(current); if(t)drawLine(current,t); } });
    })();
    """

    return ("<style>" + css + "</style>"
            "<div id='mc-wrap'>"
            "<div id='mc-email'>" + email_inner + "</div>"
            "<div id='mc-list'><div id='mc-list-head'>" + head + "</div>" + items + "</div>"
            "<svg id='mc-svg'></svg>"
            "</div>"
            "<script>" + js + "</script>")


# ── UI helpers ────────────────────────────────────────────────────────────────

def badge(ok, warn=False):
    return "✅" if ok else ("⚠️" if warn else "❌")

def score_color(p, t):
    pct = p/t if t else 0
    return "score-pass" if pct >= 0.9 else ("score-warn" if pct >= 0.6 else "score-fail")

def swatch(h):
    return (f'<span style="display:inline-block;width:14px;height:14px;border-radius:3px;'
            f'background:{h};border:1px solid #ccc;vertical-align:middle;margin-right:4px;"></span>')

def copy_html_button(html_text, label="📋 Copy optimized HTML to clipboard"):
    """Render a clipboard copy button using base64-encoded content."""
    b64 = base64.b64encode(html_text.encode("utf-8")).decode()
    components.html(f"""
    <div style="font-family:Arial,sans-serif;">
      <button id="copybtn" onclick="doCopy()" style="
        background:#2d1a29; color:white; border:none; padding:12px 24px;
        border-radius:10px; font-size:15px; font-weight:600; cursor:pointer;
        width:100%; transition:background 0.2s; display:flex; align-items:center;
        justify-content:center; gap:8px;">
        {label}
      </button>
      <div id="copymsg" style="display:none; color:#50a76a; font-size:13px;
           margin-top:6px; text-align:center; font-weight:600;">
        ✅ Copied! Paste into Mautic with Cmd+V
      </div>
    </div>
    <script>
    function doCopy() {{
      const b64 = "{b64}";
      const text = decodeURIComponent(escape(atob(b64)));
      navigator.clipboard.writeText(text).then(() => {{
        document.getElementById("copybtn").style.background = "#50a76a";
        document.getElementById("copymsg").style.display = "block";
        setTimeout(() => {{
          document.getElementById("copybtn").style.background = "#2d1a29";
          document.getElementById("copymsg").style.display = "none";
        }}, 3000);
      }}).catch(() => {{
        alert("Copy failed — please use the download button instead.");
      }});
    }}
    </script>
    """, height=80)


# ── Main App ──────────────────────────────────────────────────────────────────

def main():
    # Header
    st.markdown(f"""
    <div class="mc-header">
      <img class="mc-logo" src="{ISOTYPE_URL}">
      <div>
        <p class="mc-title">Metricool Email Checker</p>
        <p class="mc-sub">Optimize HTML + run pre-send checklist before uploading to Mautic</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="mc-intro">
      <b>Why this exists:</b> every email we send should clear the same quality bar — no exceptions.
      Run your HTML through this checker before it goes live in Mautic and it'll catch the things that
      quietly hurt us: Gmail clipping, missing alt text, broken UTMs, off-brand colors and fonts.
      <br><br>
      <b>When to use it:</b> right before you schedule or send. Paste or upload the email, hit
      <b>Analyze &amp; Optimize</b>, and work through anything it flags. Think of it as the pre-send
      gate that makes "high quality, every time" the default.
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Input
    col_up, col_paste = st.columns([1, 2])
    with col_up:
        st.markdown("##### 📁 Upload a file")
        st.caption("Drop your exported `.html` email — up to 200 MB.")
        uploaded = st.file_uploader("Upload .html", type=["html","htm"], label_visibility="collapsed")
    with col_paste:
        st.markdown("##### 📋 Or paste HTML")
        st.caption("Paste the full HTML source straight from BEEFree or Mautic.")
        html_paste = st.text_area("Paste HTML here", height=140,
                                   placeholder="<!DOCTYPE html><html>...",
                                   label_visibility="collapsed")

    html_input = ""
    if uploaded:
        html_input = uploaded.read().decode("utf-8")
        st.success(f"Loaded **{uploaded.name}** — {len(html_input.encode())/1024:.1f} KB")
    elif html_paste.strip():
        html_input = html_paste

    go = st.button("✦  Analyze & Optimize", type="primary", use_container_width=True)

    if not go or not html_input.strip():
        st.stop()

    # Run
    with st.spinner("Optimizing + running all checks…"):
        optimized, orig_kb, opt_kb = optimize_html(html_input)
        checks = run_checks(html_input)
        preview_html = build_preview(html_input, checks)

    # Score
    check_keys = ["preheader","unsubscribe","alt_text","linked_images",
                  "utm","videos","text_style","buttons","colors","palette"]
    passed = sum(1 for k in check_keys if checks.get(k,{}).get("ok",False))
    total = len(check_keys)

    st.markdown("### Results")
    ca, cb = st.columns(2)
    with ca:
        cls = "score-pass" if checks["size"]["ok"] else "score-fail"
        icon = "✅" if checks["size"]["ok"] else "❌"
        msg = (f"{checks['size']['kb']:.1f} KB — under 102.4 KB limit"
               if checks["size"]["ok"]
               else f"{checks['size']['kb']:.1f} KB — {checks['size']['over']/1024:.1f} KB over limit")
        st.markdown(f'<div class="score-box {cls}">{icon} <b>Gmail size</b><br>{msg}</div>', unsafe_allow_html=True)
    with cb:
        cls = score_color(passed, total)
        note = "Everything looks good ✨" if passed == total else "See details below"
        st.markdown(f'<div class="score-box {cls}"><b>{passed}/{total} checks passed</b><br>{note}</div>', unsafe_allow_html=True)

    st.divider()

    # Tabs: Checklist | Visual Preview | Optimized HTML
    tab_check, tab_preview, tab_html = st.tabs(["📋 Checklist", "🔍 Visual Preview", "📦 Optimized HTML"])

    # ── Tab: Optimized HTML ───────────────────────────────────────────────────
    with tab_html:
        pending = total - passed
        if pending > 0:
            st.warning(
                f"⚠️ **This HTML is optimized, but {pending} check(s) still have issues to fix.** "
                "The optimizer only shrinks and cleans the code — it does NOT fix the problems "
                "flagged in the Checklist (alt text, UTMs, off-brand colors, etc.). "
                "Review those before sending; otherwise you'll ship the same issues, just smaller."
            )

        size_label = f"{orig_kb:.1f} KB → {opt_kb:.1f} KB  ({(1-opt_kb/orig_kb)*100:.0f}% smaller)"
        if len(optimized.encode()) <= GMAIL_LIMIT:
            st.success(f"✅ {opt_kb:.1f} KB — Gmail will show the full email.")
        else:
            st.warning(f"⚠️ {opt_kb:.1f} KB — still over the limit. Consider splitting.")

        st.markdown(f"**{size_label}**")
        st.caption("Use the button below to copy — or use the download if clipboard doesn't work.")

        copy_html_button(optimized)

        st.download_button("⬇️ Download as .html file", data=optimized,
                           file_name="email-optimized.html", mime="text/html",
                           use_container_width=True)

        with st.expander("View raw HTML code"):
            st.code(optimized, language="html")

    # ── Tab: Checklist ────────────────────────────────────────────────────────
    with tab_check:
        c = checks

        # Structure
        with st.expander(f"{badge(c['preheader']['ok'] and c['unsubscribe']['ok'])}  Structure",
                         expanded=not(c['preheader']['ok'] and c['unsubscribe']['ok'])):
            col1, col2 = st.columns(2)
            with col1:
                if c["preheader"]["ok"]:
                    st.success(f"✅ Preheader: _{c['preheader']['text'][:70]}_")
                else:
                    st.error('❌ No preheader — add `<div class="preheader">` in BEEFree')
            with col2:
                if c["unsubscribe"]["ok"]:
                    st.success("✅ `{unsubscribe_text}` token present")
                else:
                    st.error("❌ `{unsubscribe_text}` missing from footer")

        # Images
        with st.expander(f"{badge(c['alt_text']['ok'] and c['linked_images']['ok'])}  Images",
                         expanded=not(c['alt_text']['ok'] and c['linked_images']['ok'])):
            if c["alt_text"]["ok"]:
                st.success("✅ All images have alt text")
            else:
                st.error(f"❌ {len(c['alt_text']['missing'])} image(s) missing alt text:")
                for item in c["alt_text"]["missing"]:
                    st.code(item["src"], language=None)
            if c["linked_images"]["ok"]:
                st.success("✅ No linked logos or headers")
            else:
                st.warning(f"⚠️ {len(c['linked_images']['flagged'])} logo/header image(s) have links — check if intentional:")
                for h in c["linked_images"]["flagged"]: st.code(h, language=None)
            st.info("💡 Width ≥95% · Alt text with keywords (e.g. *LinkedIn feature Metricool*) · Images <1 MB, GIFs <3 MB · Rounded corners only if aligned with block edges")

        # Links & UTMs
        with st.expander(f"{badge(c['utm']['ok'])}  Links & UTMs",
                         expanded=not c['utm']['ok']):
            if c["utm"]["ok"]:
                st.success("✅ All metricool.com CTAs have UTM parameters")
            else:
                st.error(f"❌ {len(c['utm']['missing'])} metricool.com link(s) missing UTMs:")
                for item in c["utm"]["missing"]:
                    st.markdown(f"**→ {item['text']}**")
                    st.code(item["href"], language=None)
            st.info("💡 UTM values must match campaign name, date, quarter, language. Check footer + Metricool logo URL.")

        # Videos
        with st.expander(f"{badge(c['videos']['ok'])}  Videos", expanded=not c['videos']['ok']):
            if c["videos"]["ok"]: st.success("✅ All videos from YouTube")
            else:
                st.error("❌ Non-YouTube video(s):")
                for s in c["videos"]["flagged"]: st.code(s, language=None)
            st.info("💡 YouTube only. BEEFree: Content → Video → paste YouTube link.")

        # Text styling
        with st.expander(f"{badge(c['text_style']['ok'])}  Text styling",
                         expanded=not c['text_style']['ok']):
            if c["text_style"]["has_arial"]: st.success("✅ Font Arial present")
            else: st.error("❌ Arial not detected — check font declarations")

            if not c["text_style"]["issues"]:
                st.success("✅ Text colors on-brand")
            else:
                st.error(f"❌ {len(c['text_style']['issues'])} text element(s) with unexpected colors:")
                for issue in c["text_style"]["issues"]:
                    col_a, col_b = st.columns([1, 4])
                    with col_a:
                        st.markdown(f'{swatch(issue["color"])} `{issue["color"]}`',
                                    unsafe_allow_html=True)
                    with col_b:
                        st.markdown(f'_{issue["text"]}_')
            st.info("💡 Arial · 16px · `#2d1a29` · letter-spacing 0")

        # Buttons
        with st.expander(f"{badge(c['buttons']['ok'])}  Buttons", expanded=not c['buttons']['ok']):
            if c["buttons"]["ok"]: st.success("✅ Button styles correct")
            else:
                st.error("❌ Button issues:")
                for i in c["buttons"]["issues"]: st.markdown(f"- {i}")
            st.info("💡 16px · ALL CAPS · border-radius 14 · padding T5/B5/L25/R25 · border T1/R3/B8/L1")

        # Colors
        with st.expander(f"{badge(c['colors']['ok'])}  Color combinations",
                         expanded=not c['colors']['ok']):
            if c["colors"]["found"]:
                uniq = sorted(set(c["colors"]["found"]))
                cols = st.columns(min(len(uniq), 5))
                for i, name in enumerate(uniq):
                    hx = BRAND_COLORS.get(name,"#ccc")
                    with cols[i % len(cols)]:
                        st.markdown(f'{swatch(hx)} {name}<br><small style="color:#888">{hx}</small>',
                                    unsafe_allow_html=True)
                st.markdown("")
            if c["colors"]["ok"]:
                st.success("✅ No incompatible color pairs in touching elements")
            else:
                st.error("❌ Incompatible touching combinations — may hurt readability:")
                for conflict in c["colors"]["conflicts"]:
                    c1, c2 = conflict["c1"], conflict["c2"]
                    h1, h2 = BRAND_COLORS.get(c1,"#ccc"), BRAND_COLORS.get(c2,"#ccc")
                    st.markdown(f'{swatch(h1)} **{c1}** + {swatch(h2)} **{c2}**',
                                unsafe_allow_html=True)
                    if conflict["context"]:
                        st.caption(f"Found near: _{' / '.join(conflict['context'])}_")
            st.info("💡 Only colors that touch (text on its background, or a block stacked on another) are checked. Deep Purple + Yellow go with everything. Blue↔Light Blue, Green↔Light Green, Orange↔Light Orange. Pink only with Deep Purple/Yellow.")

        # Palette
        with st.expander(f"{badge(c['palette']['ok'])}  Palette",
                         expanded=not c['palette']['ok']):
            if c["palette"]["ok"]:
                st.success("✅ Every color used is in the brand palette")
            else:
                st.warning(f"⚠️ {len(c['palette']['off'])} color(s) used that are NOT in the brand palette:")
                for item in c["palette"]["off"]:
                    col_a, col_b = st.columns([1, 4])
                    with col_a:
                        st.markdown(f'{swatch(item["hex"])} `{item["hex"]}`', unsafe_allow_html=True)
                    with col_b:
                        st.markdown(f'_{item["context"]}_' if item["context"] else "_(no nearby text)_")
            st.info("💡 Only these 10 hexes are allowed (text, background or border): "
                    "Yellow #E7FF56 · Deep Purple #2D1A29 · Pink #F87FDD · Stone/Grey #85B1BD · "
                    "Green #50A76A · Light Green #D0E9D7 · Orange #FB5124 · Light Orange #FFC3A1 · "
                    "Blue #596CF2 · Light Blue #D5F0FE. "
                    "White is allowed for backgrounds; black is not — our black is Deep Purple #2D1A29.")

        # Brand voice
        with st.expander("✍️  Brand voice — manual check required"):
            st.warning(
                "**Brand voice not checked automatically in v1.**\n\n"
                "Review copy against Metricool's voice:\n"
                "- Conversational and direct, never corporate-speak\n"
                "- Second person (tú / you), friendly but professional\n"
                "- Emojis sparingly and purposefully\n"
                "- No passive voice on CTAs\n"
                "- Short, punchy, scannable sentences\n\n"
                "👉 **Brand voice skill available for Claude Code** — "
                "download it and run `/metricool-brand-voice` on any text."
            )
            with st.expander("📥 How to install the brand voice skill"):
                st.markdown("""
**Step 1 — Download the skill file**

👉 [Download metricool-brand-voice.skill](https://github.com/sendgoodemailscom/metricool-email-checker/raw/main/metricool-brand-voice.skill)

**Step 2 — Install it**

Open Claude Code in your project folder and run:
```
/configure
```
When it asks about skills, drop the `.skill` file into the chat.

Or manually: unzip the `.skill` file and place `SKILL.md` inside:
```
your-project/.claude/skills/metricool-brand-voice/SKILL.md
```

**Step 3 — Use it**

In Claude Code, paste your email copy and run:
```
/metricool-brand-voice
```
""")

        # Manual checks
        st.divider()
        st.info("📋 **Make sure you've reviewed all of these before sending your email.**")
        st.markdown("""
- [ ] Subject line set in Mautic (not just BEEFree)
- [ ] Email name follows convention: `YYYYMM-Campaign-Name-LANG`
- [ ] Footer language matches email language
- [ ] Preview in BEEFree → check mobile view
- [ ] All links manually clicked and verified
- [ ] Copyright year in footer is current
- [ ] Brand voice reviewed (see section above)
""")

    # ── Tab: Visual Preview ───────────────────────────────────────────────────
    with tab_preview:
        st.caption("🟠 Missing alt text · 🔵 Missing UTM · 🔴 Off-brand text color — "
                   "hover an item in the right-hand list to jump to it and trace the connector line.")
        components.html(preview_html, height=880, scrolling=False)


if __name__ == "__main__":
    main()
