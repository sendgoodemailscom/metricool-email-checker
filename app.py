import re
import os
import subprocess
import tempfile

import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="Metricool Email Checker", page_icon="📧", layout="wide")

st.markdown("""
<style>
  .score-box { padding:1rem 1.5rem; border-radius:12px; margin-bottom:0.5rem; }
  .score-pass { background:#d0e9d7; border-left:4px solid #50a76a; }
  .score-warn { background:#fff3ed; border-left:4px solid #fb5124; }
  .score-fail { background:#ffeaea; border-left:4px solid #e0003c; }
  div[data-testid="stExpander"] { border:1px solid #e8e8e8; border-radius:10px; margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)

GMAIL_LIMIT = 102_400

BRAND_COLORS = {
    "Yellow": "#e7ff56", "Deep Purple": "#2d1a29", "Pink": "#f87fdd",
    "Green": "#50a76a", "Light Green": "#d0e9d7", "Orange": "#fb5124",
    "Light Orange": "#ffc3a1", "Blue": "#596cf2", "Light Blue": "#d5f0fe",
    "Stone/Grey": "#85b1bd",
}
HEX_TO_NAME = {v: k for k, v in BRAND_COLORS.items()}

COMPATIBLE = {
    "Deep Purple": {"Deep Purple","Yellow","Pink","Green","Light Green","Orange","Light Orange","Blue","Light Blue","Stone/Grey"},
    "Yellow":      {"Deep Purple","Yellow","Pink","Green","Light Green","Orange","Light Orange","Blue","Light Blue","Stone/Grey"},
    "Pink":        {"Deep Purple","Yellow","Pink"},
    "Blue":        {"Deep Purple","Yellow","Blue","Light Blue"},
    "Light Blue":  {"Deep Purple","Yellow","Blue","Light Blue"},
    "Orange":      {"Deep Purple","Yellow","Orange","Light Orange"},
    "Light Orange":{"Deep Purple","Yellow","Orange","Light Orange"},
    "Green":       {"Deep Purple","Yellow","Green","Light Green"},
    "Light Green": {"Deep Purple","Yellow","Green","Light Green"},
    "Stone/Grey":  {"Deep Purple","Yellow","Stone/Grey"},
}

SKIP = ["unsubscribe","mailto:","tally.so","instagram.com","twitter.com","youtube.com",
        "linkedin.com","facebook.com","tiktok.com","pinterest.com","threads.net",
        "bsky.app","docs.google","politica-privacidad","#"]


def local_minify(html):
    html = re.sub(r"<!--(?!\[if).*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r">\s+<", "><", html)
    html = re.sub(r"\s{2,}", " ", html)
    html = re.sub(r'\s*=\s*"', '="', html)
    html = "".join(l.strip() for l in html.splitlines())
    html = re.sub(r'="([a-zA-Z0-9_:;.#%,\-]+)"', r"=\1", html)
    return html


def toptal_minify(html):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", encoding="utf-8", delete=False) as f:
        f.write(html); tmp = f.name
    try:
        r = subprocess.run(
            ["curl","-s","-X","POST","https://www.toptal.com/developers/html-minifier/api/raw",
             "-H","Content-Type: application/x-www-form-urlencoded","-A","Mozilla/5.0",
             "--data-urlencode",f"input@{tmp}",
             "--data","remove_comments=1&collapse_whitespace=1&remove_redundant_attributes=1&remove_empty_attributes=1"],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip().startswith("<"):
            return r.stdout
    except Exception:
        pass
    finally:
        os.unlink(tmp)
    return local_minify(html)


def cleanup(html):
    html = re.sub(r"\s*<link[^>]+googleapis[^>]+>", "", html)
    for pat in [r"<!--\[if mso\]>\s*<xml>.*?</xml>\s*<!\[endif\]-->",
                r"<!--\[if mso \]><style>.*?</style>\s*<!\[endif\]-->",
                r"<!--\[if mso\]>\s*<v:roundrect.*?<!\[endif\]-->",
                r"<!--\[if vml\]>.*?<!\[endif\]-->",
                r"<!--\[if \(mso\)\|\(IE\)\]>.*?<!\[endif\]-->"]:
        html = re.sub(pat, "", html, flags=re.DOTALL)
    html = html.replace("<!--[if !vml]><!-->", "")
    html = html.replace(' role="presentation"', "").replace(" role=presentation", "")
    html = re.sub(r"mso-table-lspace:\s*0pt;\s*mso-table-rspace:\s*0pt;\s*", "", html)
    html = html.replace(" style=mso-table-lspace:0pt;mso-table-rspace:0pt>", ">")
    html = re.sub(r"\s+style=mso-table-lspace:0pt;mso-table-rspace:0pt\b", "", html)
    html = re.sub(r";?\s*mso-line-height-alt:[^;>\"']+", "", html)
    for pat in [r'<span style="word-break:break-word;">(.*?)</span>',
                r'<span style="word-break: break-word;">(.*?)</span>']:
        html = re.sub(pat, r"\1", html, flags=re.DOTALL)
    html = re.sub(r";?\s*word-break:\s*break-word", "", html)
    html = re.sub(r";?\s*box-sizing:\s*\w[\w-]*(?=[;>\"'\s])", "", html)
    html = html.replace("<tbody>", "").replace("</tbody>", "")
    for s in ["border-radius: 0;","border-radius:0;","border-radius:0 0 0 0;",
              "font-weight: 400;","font-weight:400;","background-size: auto;",
              "background-size:auto;","background-image: none;",
              "background-position: top left;","letter-spacing: normal;",
              "letter-spacing:normal;","letter-spacing:0;","mso-border-alt: none;",
              "mso-border-alt:none;","direction:ltr;","direction: ltr;",
              "margin-top:0;margin-bottom:0;","background-image:url('');",
              "background-repeat: no-repeat;"]:
        html = html.replace(s, "")
    html = html.replace(' height="auto"', "").replace(" height=auto", "")
    html = re.sub(r'\s+border="0"', "", html)
    html = re.sub(r'\s+cellpadding="0"\s+cellspacing="0"', "", html)
    html = re.sub(r";?\s*min-width:\s*\d+px(?=[;>\"'\s])", "", html)
    for a in [r'\s+align="center"',r'\s+align="left"',r'\s+valign="middle"',r"\s+valign=middle"]:
        html = re.sub(a, "", html)
    html = re.sub(r"(<td[^>]*)\s+width=100%", r"\1", html)
    html = re.sub(r'(<td[^>]*)\s+width="100%"', r"\1", html)
    html = html.replace(";text-align:left", "").replace("text-align:left;", "")
    html = html.replace(";vertical-align:top", "").replace("vertical-align:top;", "")
    for o, n in [("font-family:Arial,'Helvetica Neue',Helvetica,sans-serif","font-family:Arial,sans-serif"),
                 ("font-family: Arial, 'Helvetica Neue', Helvetica, sans-serif","font-family:Arial,sans-serif"),
                 ("font-family: Arial, sans-serif","font-family:Arial,sans-serif"),
                 ("Nunito, Arial, Helvetica Neue, Helvetica, sans-serif","Arial,sans-serif"),
                 ("Nunito,Arial,Helvetica Neue,Helvetica,sans-serif","Arial,sans-serif")]:
        html = html.replace(o, n)
    html = re.sub(r'\s+style=""', "", html)
    return html


def optimize_html(html):
    ok = len(html.encode()) / 1024
    html = toptal_minify(html)
    html = cleanup(html)
    return html, ok, len(html.encode()) / 1024


def run_checks(html):
    soup = BeautifulSoup(html, "html.parser")
    r = {}
    size = len(html.encode())
    r["size"] = {"kb": size/1024, "ok": size <= GMAIL_LIMIT, "over": max(0, size-GMAIL_LIMIT)}
    ph = soup.find(class_="preheader")
    ph_text = ph.get_text(strip=True) if ph else ""
    r["preheader"] = {"ok": bool(ph_text), "text": ph_text}
    r["unsubscribe"] = {"ok": "{unsubscribe_text}" in html}
    noise = ["spacer","ratio","getbee","1x1","video_ratio"]
    missing_alt = [img.get("src","(no src)")[:80] for img in soup.find_all("img")
                   if not img.get("alt","").strip() and not any(n in img.get("src","").lower() for n in noise)]
    r["alt_text"] = {"ok": not missing_alt, "missing": missing_alt}
    linked_logo = [a.get("href","")[:80] for a in soup.find_all("a")
                   if a.find("img") and any(k in a.find("img").get("src","").lower()
                   for k in ["logo","header","banner","vector"])]
    r["linked_images"] = {"ok": not linked_logo, "flagged": linked_logo}
    missing_utm = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"): continue
        if any(s in href for s in SKIP): continue
        if not all(p in href for p in ["utm_source","utm_medium","utm_campaign"]):
            missing_utm.append(href[:90])
    r["utm"] = {"ok": not missing_utm, "missing": missing_utm}
    bad_vid = [a.get("href","")[:80] for a in soup.find_all("a", class_="video-preview")
               if a.get("href","") and "youtube" not in a.get("href","") and "youtu.be" not in a.get("href","")]
    bad_vid += [i["src"][:80] for i in soup.find_all("iframe", src=True)
                if "youtube" not in i["src"] and "youtu.be" not in i["src"]]
    r["videos"] = {"ok": not bad_vid, "flagged": bad_vid}
    styles = " ".join(t.get("style","") for t in soup.find_all(True))
    has_arial = "arial" in styles.lower()
    allowed = {"#2d1a29","#ffffff","#fff","#1a1a1a","#596cf2","#00a4ce","#50a76a","#d5f0fe","#2d1a2a"}
    bad_colors = [c.lower() for c in re.findall(r'color:\s*(#[0-9a-fA-F]{3,6})', styles)
                  if c.lower() not in allowed]
    r["text_style"] = {"ok": has_arial and not bad_colors, "has_arial": has_arial, "bad_colors": bad_colors}
    btn_issues = []
    for btn in soup.find_all(class_="button"):
        s = btn.get("style","").replace(" ","")
        t = btn.get_text(strip=True)
        if len(t) > 3 and t != t.upper(): btn_issues.append(f"Not uppercase: '{t[:40]}'")
        if not any(f"border-radius:{x}px" in s for x in ["14","16"]):
            btn_issues.append(f"Border-radius not 14/16px: '{t[:30]}'")
    r["buttons"] = {"ok": not btn_issues, "issues": list(dict.fromkeys(btn_issues))}
    bg = {c.lower() for c in re.findall(r'background-color:\s*(#[0-9a-fA-F]{3,6})', html)}
    named = [HEX_TO_NAME[c] for c in bg if c in HEX_TO_NAME]
    conflicts, seen = [], set()
    for i, c1 in enumerate(named):
        for c2 in named[i+1:]:
            if c1 == c2: continue
            pair = tuple(sorted([c1,c2]))
            if pair in seen: continue
            seen.add(pair)
            if c2 not in COMPATIBLE.get(c1, set()): conflicts.append((c1, c2))
    r["colors"] = {"ok": not conflicts, "found": named, "conflicts": conflicts}
    return r


def badge(ok, warn=False):
    return "✅" if ok else ("⚠️" if warn else "❌")

def score_color(p, t):
    pct = p/t if t else 0
    return "score-pass" if pct >= 0.9 else ("score-warn" if pct >= 0.6 else "score-fail")

def swatch(h):
    return f'<span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:{h};border:1px solid #ccc;vertical-align:middle;margin-right:4px;"></span>'


def main():
    c1, c2 = st.columns([1, 8])
    with c1: st.markdown("## 📧")
    with c2:
        st.markdown("## Metricool Email Checker")
        st.caption("Paste HTML or upload a file to optimize it and run the pre-send checklist.")
    st.divider()

    uploaded = st.file_uploader("Upload .html file", type=["html","htm"], label_visibility="collapsed")
    html_input = ""
    if uploaded:
        html_input = uploaded.read().decode("utf-8")
        st.success(f"Loaded **{uploaded.name}** ({len(html_input.encode())/1024:.1f} KB)")
    else:
        html_input = st.text_area("Or paste HTML here", height=180,
                                   placeholder="<!DOCTYPE html>\n<html>...",
                                   label_visibility="visible")

    if not st.button("✦  Analyze & Optimize", type="primary", use_container_width=True) or not html_input.strip():
        st.stop()

    with st.spinner("Optimizing + running checks…"):
        optimized, orig_kb, opt_kb = optimize_html(html_input)
        chk = run_checks(html_input)

    keys = ["preheader","unsubscribe","alt_text","linked_images","utm","videos","text_style","buttons","colors"]
    passed = sum(1 for k in keys if chk.get(k,{}).get("ok", False))
    total = len(keys)

    st.markdown("### Results")
    col_a, col_b = st.columns(2)
    with col_a:
        cls = "score-pass" if chk["size"]["ok"] else "score-fail"
        icon = "✅" if chk["size"]["ok"] else "❌"
        msg = f"{chk['size']['kb']:.1f} KB — under 102.4 KB" if chk["size"]["ok"] else f"{chk['size']['kb']:.1f} KB — {chk['size']['over']/1024:.1f} KB over"
        st.markdown(f'<div class="score-box {cls}">{icon} <b>Gmail size</b><br>{msg}</div>', unsafe_allow_html=True)
    with col_b:
        cls = score_color(passed, total)
        st.markdown(f'<div class="score-box {cls}"><b>{passed}/{total} checks passed</b><br>{"Everything looks good ✨" if passed==total else "See details below"}</div>', unsafe_allow_html=True)

    st.divider()

    with st.expander(f"📦 Optimized HTML — {orig_kb:.1f} KB → {opt_kb:.1f} KB ({(1-opt_kb/orig_kb)*100:.0f}% smaller)", expanded=True):
        st.caption("Ready to paste into Mautic. Use the copy button ↗ on the code block.")
        if len(optimized.encode()) <= GMAIL_LIMIT:
            st.success(f"✅ {opt_kb:.1f} KB — Gmail will show this email in full.")
        else:
            st.warning(f"⚠️ {opt_kb:.1f} KB — still over the limit. Consider splitting the email.")
        st.code(optimized, language="html")
        st.download_button("⬇️ Download optimized HTML", data=optimized, file_name="email-optimized.html", mime="text/html")

    st.markdown("### Pre-send checklist")

    with st.expander(f"{badge(chk['preheader']['ok'] and chk['unsubscribe']['ok'])}  Structure",
                     expanded=not (chk['preheader']['ok'] and chk['unsubscribe']['ok'])):
        ca, cb = st.columns(2)
        with ca:
            if chk["preheader"]["ok"]: st.success(f"✅ Preheader: _{chk['preheader']['text'][:60]}_")
            else: st.error('❌ No preheader — add `<div class="preheader">` in BEEFree')
        with cb:
            if chk["unsubscribe"]["ok"]: st.success("✅ `{unsubscribe_text}` present")
            else: st.error("❌ Missing `{unsubscribe_text}` token")

    with st.expander(f"{badge(chk['alt_text']['ok'] and chk['linked_images']['ok'])}  Images",
                     expanded=not (chk['alt_text']['ok'] and chk['linked_images']['ok'])):
        if chk["alt_text"]["ok"]: st.success("✅ All images have alt text")
        else:
            st.error(f"❌ {len(chk['alt_text']['missing'])} image(s) missing alt text:")
            for s in chk["alt_text"]["missing"]: st.code(s, language=None)
        if chk["linked_images"]["ok"]: st.success("✅ No linked logos or headers")
        else:
            st.warning(f"⚠️ {len(chk['linked_images']['flagged'])} logo/header image(s) have links — intentional?")
            for h in chk["linked_images"]["flagged"]: st.code(h, language=None)
        st.info("💡 Width ≥95% · Alt text with keywords · Images <1 MB, GIFs <3 MB · Rounded corners only if aligned with block edges.")

    with st.expander(f"{badge(chk['utm']['ok'])}  Links & UTMs", expanded=not chk['utm']['ok']):
        if chk["utm"]["ok"]: st.success("✅ All CTA links have UTM parameters")
        else:
            st.error(f"❌ {len(chk['utm']['missing'])} link(s) missing utm_source / utm_medium / utm_campaign:")
            for h in chk["utm"]["missing"]: st.code(h, language=None)
        st.info("💡 UTM values must match campaign name, date, quarter and language. Check footer + Metricool logo URL.")

    with st.expander(f"{badge(chk['videos']['ok'])}  Videos", expanded=not chk['videos']['ok']):
        if chk["videos"]["ok"]: st.success("✅ All videos from YouTube")
        else:
            st.error("❌ Non-YouTube video(s) found:")
            for s in chk["videos"]["flagged"]: st.code(s, language=None)
        st.info("💡 YouTube only. BEEFree: Content → Video → paste YouTube link.")

    with st.expander(f"{badge(chk['text_style']['ok'])}  Text styling", expanded=not chk['text_style']['ok']):
        if chk["text_style"]["has_arial"]: st.success("✅ Font Arial found")
        else: st.error("❌ Arial not detected")
        if not chk["text_style"]["bad_colors"]: st.success("✅ Text colors on-brand")
        else:
            st.warning("⚠️ Unexpected text color(s) — verify intentional:")
            for col in chk["text_style"]["bad_colors"]: st.markdown(f"{swatch(col)} `{col}`", unsafe_allow_html=True)
        st.info("💡 Arial · 16px · #2d1a29 · letter-spacing 0")

    with st.expander(f"{badge(chk['buttons']['ok'])}  Buttons", expanded=not chk['buttons']['ok']):
        if chk["buttons"]["ok"]: st.success("✅ Button styles correct")
        else:
            st.error("❌ Button issues:")
            for i in chk["buttons"]["issues"]: st.markdown(f"- {i}")
        st.info("💡 16px · ALL CAPS · border-radius 14 · padding T5/B5/L25/R25 · border T1/R3/B8/L1")

    with st.expander(f"{badge(chk['colors']['ok'])}  Color combinations", expanded=not chk['colors']['ok']):
        if chk["colors"]["found"]:
            uniq = sorted(set(chk["colors"]["found"]))
            cols = st.columns(min(len(uniq), 5))
            for i, name in enumerate(uniq):
                hx = BRAND_COLORS.get(name, "#ccc")
                with cols[i % len(cols)]:
                    st.markdown(f'{swatch(hx)} {name}<br><small style="color:#888">{hx}</small>', unsafe_allow_html=True)
            st.markdown("")
        if chk["colors"]["ok"]: st.success("✅ No incompatible color pairs")
        else:
            st.error("❌ Incompatible combinations:")
            for c1, c2 in chk["colors"]["conflicts"]:
                st.markdown(f'{swatch(BRAND_COLORS.get(c1,"#ccc"))} **{c1}** + {swatch(BRAND_COLORS.get(c2,"#ccc"))} **{c2}**', unsafe_allow_html=True)
        st.info("💡 Deep Purple + Yellow go with everything. Blue↔Light Blue, Green↔Light Green, Orange↔Light Orange. Pink only with Deep Purple/Yellow.")

    with st.expander("✍️  Brand voice — manual check required"):
        st.warning(
            "**Brand voice is not checked automatically in v1.**\n\n"
            "Review against Metricool's voice guidelines:\n"
            "- Conversational, never corporate-speak\n"
            "- Second person (tú / you), friendly but professional\n"
            "- Emojis used sparingly\n"
            "- No passive voice on CTAs\n"
            "- Short, punchy, scannable sentences\n\n"
            "👉 Use the **brand voice skill** in Claude Code for an AI-powered review."
        )

    st.divider()
    st.markdown("#### 📋 Manual checks")
    st.markdown("""
- [ ] Subject line set in Mautic
- [ ] Email name: `YYYYMM-Campaign-Name-LANG`
- [ ] Footer language matches email language
- [ ] Mobile preview in BEEFree
- [ ] All links clicked and verified
- [ ] Copyright year in footer is current
""")


if __name__ == "__main__":
    main()
