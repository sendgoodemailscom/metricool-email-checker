import re
import os
import base64
import subprocess
import tempfile

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

  .score-box  { padding:14px 20px; border-radius:12px; margin-bottom:6px; font-family:inherit; }
  .score-pass { background:#d0e9d7; border-left:4px solid #50a76a; }
  .score-warn { background:#fff3ed; border-left:4px solid #fb5124; }
  .score-fail { background:#ffeaea; border-left:4px solid #e0003c; }

  div[data-testid="stExpander"] { border:1px solid #e8e8e8; border-radius:12px; margin-bottom:6px; }
  .stButton>button { font-family:'Plus Jakarta Sans',Arial,sans-serif; font-weight:600; border-radius:10px; }
  .stButton>button[kind="primary"] { background:#2d1a29; color:white; border:none; }
  .stButton>button[kind="primary"]:hover { background:#50a76a; }

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

    # Text styling — find specific elements with wrong colors
    style_issues = []
    for tag in soup.find_all(True):
        style = tag.get("style","")
        colors_in_style = re.findall(r'(?<![background-])color:\s*(#[0-9a-fA-F]{3,6})', style)
        for c in colors_in_style:
            if c.lower() not in ALLOWED_TEXT_COLORS:
                text = tag.get_text(strip=True)[:60]
                if text and len(text) > 3:
                    style_issues.append({"color": c.lower(), "text": text, "tag": tag.name})
    # Deduplicate by color+text
    seen_issues = set()
    unique_issues = []
    for i in style_issues:
        key = (i["color"], i["text"][:20])
        if key not in seen_issues:
            seen_issues.add(key)
            unique_issues.append(i)
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

    # Color combinations — find locations
    bg_hex = {c.lower() for c in re.findall(r'background-color:\s*(#[0-9a-fA-F]{3,6})', html)}
    named = [HEX_TO_NAME[c] for c in bg_hex if c in HEX_TO_NAME]
    conflicts, seen = [], set()
    for i, c1 in enumerate(named):
        for c2 in named[i+1:]:
            if c1 == c2: continue
            pair = tuple(sorted([c1, c2]))
            if pair in seen: continue
            seen.add(pair)
            if c2 not in COMPATIBLE.get(c1, set()):
                # Find section context
                h1_hex = BRAND_COLORS.get(c1,"")
                h2_hex = BRAND_COLORS.get(c2,"")
                locations = []
                for tag in soup.find_all(True):
                    style = tag.get("style","").lower().replace(" ","")
                    if h1_hex in style or h2_hex in style:
                        nearby_text = tag.get_text(strip=True)[:40]
                        if nearby_text and len(nearby_text) > 3:
                            locations.append(nearby_text)
                            if len(locations) >= 2: break
                conflicts.append({"c1": c1, "c2": c2, "context": locations[:2]})
    r["colors"] = {"ok": not conflicts, "found": named, "conflicts": conflicts}

    return r


# ── Preview annotator ─────────────────────────────────────────────────────────

def build_preview(html, checks):
    """Inject error highlights into HTML for visual preview."""
    soup = BeautifulSoup(html, "html.parser")

    errors_injected = 0

    # Mark images missing alt
    for img in soup.find_all("img"):
        if img.get("alt","").strip(): continue
        src = img.get("src","").lower()
        if any(n in src for n in NOISE_SRCS): continue
        img["title"] = "❌ Missing alt text — add descriptive alt text"
        img["style"] = img.get("style","") + ";outline:3px solid #fb5124 !important;outline-offset:2px;"
        errors_injected += 1

    # Mark links missing UTMs
    skip_exts = [".pdf",".jpg",".jpeg",".png",".gif",".webp",".svg"]
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"): continue
        if "metricool.com" not in href: continue
        if any(s in href for s in SKIP_UTM): continue
        if any(href.lower().endswith(e) for e in skip_exts): continue
        if is_footer_link(a): continue
        if not all(p in href for p in UTM_REQUIRED):
            a["title"] = f"❌ Missing UTM params — utm_source, utm_medium, utm_campaign"
            a["style"] = a.get("style","") + ";outline:3px solid #e7ff56 !important;outline-offset:2px;"
            errors_injected += 1

    # Mark text with wrong colors
    for tag in soup.find_all(True):
        style = tag.get("style","")
        colors = re.findall(r'(?<![background-])color:\s*(#[0-9a-fA-F]{3,6})', style)
        for c in colors:
            if c.lower() not in ALLOWED_TEXT_COLORS:
                tag["title"] = f"❌ Unexpected text color: {c}"
                tag["style"] = style + f";outline:3px solid #596cf2 !important;"
                errors_injected += 1
                break

    # Inject legend CSS + legend bar at top
    legend_html = f"""
    <div style="position:sticky;top:0;background:#2d1a29;color:white;padding:8px 12px;
                font-family:Arial,sans-serif;font-size:12px;z-index:9999;display:flex;gap:16px;align-items:center;">
      <strong>📍 Error preview</strong> ({errors_injected} markers — hover for details)
      <span>🟠 Alt text</span>
      <span>🟡 UTM missing</span>
      <span>🟣 Text color</span>
    </div>
    """

    # Inject into body
    body = soup.find("body")
    if body:
        legend = BeautifulSoup(legend_html, "html.parser")
        body.insert(0, legend)
    else:
        return f"<div>{legend_html}{str(soup)}</div>"

    return str(soup)


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
        <p class="mc-title">Email Checker</p>
        <p class="mc-sub">Optimize HTML + run pre-send checklist before uploading to Mautic</p>
      </div>
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
                  "utm","videos","text_style","buttons","colors"]
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

    # Tabs: Checklist | Optimized HTML | Preview
    tab_check, tab_html, tab_preview = st.tabs(["📋 Checklist", "📦 Optimized HTML", "🔍 Visual Preview"])

    # ── Tab: Optimized HTML ───────────────────────────────────────────────────
    with tab_html:
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
                st.success("✅ No incompatible color pairs")
            else:
                st.error("❌ Incompatible combinations — may hurt accessibility:")
                for conflict in c["colors"]["conflicts"]:
                    c1, c2 = conflict["c1"], conflict["c2"]
                    h1, h2 = BRAND_COLORS.get(c1,"#ccc"), BRAND_COLORS.get(c2,"#ccc")
                    st.markdown(f'{swatch(h1)} **{c1}** + {swatch(h2)} **{c2}**',
                                unsafe_allow_html=True)
                    if conflict["context"]:
                        st.caption(f"Found near: _{' / '.join(conflict['context'])}_")
            st.info("💡 Deep Purple + Yellow go with everything. Blue↔Light Blue, Green↔Light Green, Orange↔Light Orange. Pink only with Deep Purple/Yellow.")

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
        st.caption("Orange outline = missing alt text · Yellow outline = missing UTM · Purple outline = unexpected text color · Hover over elements for details")

        # Count markers
        n_errors = (len(checks["alt_text"]["missing"]) +
                    len(checks["utm"]["missing"]) +
                    len(checks["text_style"]["issues"]))

        if n_errors == 0:
            st.success("✅ No visual errors to mark — preview is clean.")
        else:
            st.warning(f"⚠️ {n_errors} issue(s) marked in the preview below.")

        components.html(preview_html, height=2400, scrolling=True)


if __name__ == "__main__":
    main()
