"""Builds the six category pages, contact, privacy and the homepage "What we do" section from content/*.json.
The client edits those JSON files through Pages CMS (.pages.yml); the GitHub Action reruns this. Locally: python3 cms/build.py"""
import html, json, os, re

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = "sms:+13473278166"
CALL = "tel:+17188891374"
INSTA = "https://www.instagram.com/ourlittlevillage.llc/"
FONTS = "https://fonts.googleapis.com/css2?family=Gloock&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&display=swap"
NAV = [("parties.html", "Parties"), ("private-events.html", "Private Events"), ("toddler-classes.html", "Classes"),
       ("art-classes.html", "Creative Arts"), ("special-events.html", "Special Events"), ("balloons-backdrops.html", "GO OLV"), ("contact.html", "Contact")]
MAPS = "https://www.google.com/maps/search/?api=1&amp;query=1732+Victory+Blvd+Staten+Island+NY+10314"
CONTACT = "contact.html"
ICONS = {"text": '<path d="M12 18h76a6 6 0 0 1 6 6v46a6 6 0 0 1-6 6H40L22 92V76H12a6 6 0 0 1-6-6V24a6 6 0 0 1 6-6Z"/>',
         "call": '<path d="M30 10 16 16C12 48 52 88 84 84l6-14-22-10-8 9c-10-5-20-15-25-25l9-8Z"/>',
         "mail": '<rect x="8" y="22" width="84" height="58" rx="7"/><path d="m10 28 40 30 40-30"/>'}
# label, main line, call to action, link, background, text color, classes, icon, photos
TILES = [("Text", "347-327-8166", "Send us a text", TEXT, "#ffbe1f", "#2a1a05", "s3", "text", []),
         ("Call", "718-889-1374", "Give us a call", CALL, "#a80f4c", "#fff", "s3", "call", []),
         ("Email", "hello@ourlittlevillage.com", "Write to us", "mailto:hello@ourlittlevillage.com", "#5228c4", "#fff", "mail s2", "mail", []),
         ("Instagram", "@ourlittlevillage.llc", "See our latest work", INSTA, "#ffc9dc", "#3f0f2c", "s4 has-fan", "", ["balloons-a", "parties-a", "private-c"]),
         ("Classes", "Ask about toddler or art classes", "Text us to sign up", TEXT, "#ffe9a8", "#053f3c", "s6 has-fan", "", ["art-a", "toddler-a", "art-b"])]

# Page order (also the "Next:" chain) and each page's locked color theme / video. Not editable in the CMS.
ORDER = [("parties.html", "parties"), ("private-events.html", "private"), ("toddler-classes.html", "toddler"),
         ("art-classes.html", "art"), ("special-events.html", "special"), ("balloons-backdrops.html", "balloons")]
# Where a CMS button can point. The editor picks one of these names, never a raw URL.
LINKS = {"text": TEXT, "call": CALL, "instagram": INSTA, "contact": "contact.html", "work": "#work"}
SPEEDS = (-34, 46, -60)


def e(s):
    return html.escape(s, quote=True)


def em(s):
    """Editor text with *word* marks -> escaped HTML with <em> (the script-font accent)."""
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", e(s))


def img(path):
    """Image paths come from the CMS media library; refuse anything else so nothing odd lands in an src."""
    if not re.fullmatch(r"/?assets/work/[\w.-]+\.(jpe?g|png|webp)", path, re.I):
        raise ValueError("unexpected image path: %r" % path)
    return path.lstrip("/")


def link(b):
    return b["label"], LINKS[b["to"]]


def load(name):
    with open(os.path.join(SITE, "content", name)) as f:
        return json.load(f)


def share(file, title, desc, card):
    """Link-preview tags (cards made by make_share_cards.py) plus the site icons."""
    base = "https://ourlittlevillage.com/"
    url = base + ("" if file == "index.html" else file)
    return f"""<link rel="canonical" href="{url}">
<link rel="icon" type="image/png" href="favicon.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="theme-color" content="#0e0b22">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Our Little Village">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{base}assets/og/{card}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(title)}, Our Little Village in Staten Island">
<meta name="twitter:card" content="summary_large_image">"""


def nav(current):
    links = "".join('<li><a href="%s"%s>%s</a></li>' % (f, ' aria-current="page"' if f == current else "", e(n)) for f, n in NAV if f != CONTACT)
    panel = '<a href="index.html">Home</a>' + "".join('<a href="%s">%s</a>' % (f, e(n)) for f, n in NAV)
    return ('<nav class="nav" aria-label="Main"><a class="brand" href="index.html"><img src="assets/logo.png" alt=""><span>Our Little Village</span></a>'
            '<ul>%s</ul><div class="nav-end"><details class="menu"><summary>Menu</summary><div class="panel-links">%s</div></details>'
            '<a class="call" href="%s">Contact us</a></div></nav>') % (links, panel, CONTACT)


def action(i, a):
    label, url = a
    ext = ' target="_blank" rel="noopener"' if url.startswith("https") else ""
    return '<a class="btn %s" href="%s"%s>%s</a>' % ("main" if i == 0 else "alt", url, ext, e(label))


def gallery(items):
    cols = [[], [], []]
    for i, it in enumerate(items):
        cols[i % 3].append(it)
    out = ""
    for s, col in zip(SPEEDS, cols):
        imgs = "".join('<img loading="lazy" src="%s" alt="%s">' % (n, e(a)) for n, a in col)
        out += '<div class="col" style="--s:%d">%s</div>' % (s, imgs)
    return out


def card(c, i):
    out = '<p class="tag">%s</p><h3>%s</h3><p class="meta">%s</p>' % (e(c["tag"]), e(c["title"]), e(c["meta"]))
    if c.get("text"):
        out += '<p class="body">%s</p>' % e(c["text"])
    if c.get("facts"):
        out += '<dl class="facts">%s</dl>' % "".join('<div><dt>%s</dt><dd>%s</dd></div>' % (e(l), e(v)) for l, v in c["facts"])
    if c.get("items"):
        out += "<ul>%s</ul>" % "".join("<li><strong>%s</strong> %s</li>" % (e(x[0]), e(x[1])) if isinstance(x, tuple) else "<li>%s</li>" % e(x) for x in c["items"])
    if c.get("chips"):
        out += '<p class="chips-label">%s</p><ul class="chips">%s</ul>' % (e(c["chips"][0]), "".join("<li>%s</li>" % e(x) for x in c["chips"][1]))
    if c.get("note"):
        out += '<p class="note"><strong>%s</strong> %s</p>' % (e(c["note"][0]), e(c["note"][1]))
    if c.get("link"):
        label, url = c["link"]
        ext = ' target="_blank" rel="noopener"' if url.startswith("https") else ""
        out += '<a class="card-link" href="%s"%s>%s <span aria-hidden="true">&rarr;</span></a>' % (url, ext, e(label))
    return '<article class="card reveal%s" style="--i:%d">%s</article>' % (" wide" if c.get("wide") else "", i, out)


def group(g):
    head = '<h2 class="group-head reveal">%s</h2>' % g["head"] if g.get("head") else ""
    if g.get("intro"):
        head += '<p class="group-intro reveal">%s</p>' % e(g["intro"])
    ribbon = ""
    if g.get("marquee"):
        run = "".join("<li>%s</li>" % e(x) for x in g["marquee"])
        # second copy makes the loop seamless; screen readers get the first list only
        ribbon = '<div class="ribbon"><ul class="run">%s</ul><ul class="run" aria-hidden="true">%s</ul></div>' % (run, run)
    note = '<p class="group-note reveal">%s</p>' % e(g["note"]) if g.get("note") else ""
    cards = "".join(card(c, i) for i, c in enumerate(g["cards"]))
    return '<section class="details">%s%s<div class="cards">%s</div>%s</section>' % (head, ribbon, cards, note)


def to_page(d, file, clip):
    """Content-file shape (what the CMS edits) -> the shape the templates below use. Blank optional fields drop out."""
    def card(c):
        return dict(tag=c["tag"], title=c["title"], meta=c["subtitle"], text=c.get("text", ""), wide=c.get("wide", False),
                    facts=[(f["label"], f["value"]) for f in c.get("facts") or []],
                    items=[(b["bold"], b["text"]) if b.get("bold") else b["text"] for b in c.get("bullets") or []],
                    chips=(c["chips"]["label"], c["chips"]["list"]) if (c.get("chips") or {}).get("list") else None,
                    note=(c["note"]["label"], c["note"]["text"]) if (c.get("note") or {}).get("text") else None,
                    link=link(c["button"]) if (c.get("button") or {}).get("label") else None)
    return dict(file=file, clip=clip, title=d["title"], h1=em(d["heading"]), seo=d["description"], lede=d["intro"],
                actions=[link(b) for b in d["buttons"]], statement=em(d["statement"]),
                groups=[dict(head=em(g["heading"]) if g.get("heading") else "", intro=g.get("intro", ""), marquee=g.get("ribbon") or [],
                             note=g.get("note", ""), cards=[card(c) for c in g["cards"]]) for g in d["sections"]],
                float=(img(d["photo"]["image"]), d["photo"]["alt"]), gallery=[(img(g["image"]), g["alt"]) for g in d["gallery"]])


def what_we_do(d):
    """The homepage "What we do" panels. Order, colors, numbers and links stay fixed; text and photos come from home.json."""
    out = '  <header class="offer-head"><h2>%s</h2><p>%s</p></header>\n\n' % (em(d["heading"]), e(d["intro"]))
    for n, (file, clip) in enumerate(ORDER):
        c = d["panels"][clip]
        out += ('  <article class="ch" data-clip="%s">\n    <div class="ch-text"><span class="num">%02d</span><h3>%s</h3><p>%s</p><a class="more" href="%s">%s</a></div>\n'
                '    <div class="ch-media"><div class="arch"></div>\n      <img class="float a" loading="lazy" src="%s" alt="%s">\n'
                '      <img class="float b" loading="lazy" src="%s" alt="%s"></div>\n  </article>\n') % (
            clip, n + 1, em(c["heading"]), e(c["text"]), file, e(c["button"]),
            img(c["photo_1"]["image"]), e(c["photo_1"]["alt"]), img(c["photo_2"]["image"]), e(c["photo_2"]["alt"]))
    return out + "\n"


def page(p, nxt):
    cta = "".join(action(i, a) for i, a in enumerate(p["actions"]))
    first = p["actions"][0]
    closing = [first, ("Follow us on Instagram", INSTA)] if first[1] == "contact.html" else [first, ("Get in touch", "contact.html")]
    closing_cta = "".join(action(i, a) for i, a in enumerate(closing))
    blocks = "".join(group(g) for g in p["groups"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(p['title'])} | Our Little Village, Staten Island</title>
<meta name="description" content="{e(p['seo'])}">
{share(p['file'], p['title'] + ' | Our Little Village', p['seo'], p['file'][:-5])}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<link rel="stylesheet" href="assets/pages.css">
<link rel="stylesheet" href="assets/access.css">
</head>
<body data-theme="{p['clip']}">
<a class="skip-link" href="#content">Skip to content</a>
<header class="panel">
{nav(p['file'])}
<section class="phero" id="content" tabindex="-1">
  <div class="fx">
    <p class="crumb"><a href="index.html">Our Little Village</a></p>
    <h1>{p['h1']}</h1>
    <p class="lede">{e(p['lede'])}</p>
    <div class="cta">{cta}</div>
  </div>
  <div class="stage">
    <div class="arch"><video muted loop playsinline preload="none" poster="assets/work/{p['clip']}.jpg" data-src="assets/work/{p['clip']}.mp4" aria-hidden="true"></video></div>
    <img class="float" src="{p['float'][0]}" alt="{e(p['float'][1])}">
  </div>
</section>
</header>
<main>
  <section class="statement"><h2 class="reveal">{p['statement']}</h2></section>
  {blocks}
  <section class="gallery-wrap" id="work"><div class="gallery reveal">{gallery(p['gallery'])}</div>
    <p class="gallery-note"><a href="{INSTA}" target="_blank" rel="noopener">See more on Instagram</a></p></section>
</main>
<section class="next dark">
  <h2 class="reveal">Let's plan <em>something.</em></h2>
  <div class="cta">{closing_cta}</div>
  <a class="next-link" href="{nxt['file']}">Next: {e(nxt['title'])} &rarr;</a>
</section>
<footer><div><span>Our Little Village</span><span>1732 Victory Blvd, Staten Island, NY 10314</span><a href="{CALL}">Call 718-889-1374</a><a href="{TEXT}">Text 347-327-8166</a><a href="mailto:hello@ourlittlevillage.com">hello@ourlittlevillage.com</a><a href="privacy.html">Privacy Policy</a><span>&copy; 2026 Our Little Village LLC. All rights reserved.</span></div></footer>
<script src="assets/motion.js"></script>
<script src="assets/pages.js"></script>
</body>
</html>
"""


def contact_page():
    tiles = ""
    for label, main, hint, url, bg, fg, cls, icon, photos in TILES:
        ext = ' target="_blank" rel="noopener"' if url.startswith("https") else ""
        art = '<svg class="tile-icon" viewBox="0 0 100 100" aria-hidden="true">%s</svg>' % ICONS[icon] if icon else ""
        if photos:
            art = '<div class="fan" aria-hidden="true">%s</div>' % "".join('<img loading="lazy" src="assets/work/%s.jpg" alt="">' % n for n in photos)
        tiles += '<a class="tile reveal %s" style="--t:%s;--c:%s" href="%s"%s>%s<small>%s</small><strong>%s</strong><span>%s &rarr;</span></a>' % (cls, bg, fg, url, ext, art, e(label), e(main).replace("hello@", "hello@<wbr>").replace("village.llc", "village<wbr>.llc"), e(hint))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contact | Our Little Village, Staten Island</title>
<meta name="description" content="Call, text, email or visit Our Little Village at 1732 Victory Blvd, Staten Island, NY 10314.">
{share('contact.html', "Let's plan something | Our Little Village", 'Call, text, email or visit Our Little Village at 1732 Victory Blvd, Staten Island, NY 10314.', 'contact')}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<link rel="stylesheet" href="assets/pages.css">
<link rel="stylesheet" href="assets/access.css">
</head>
<body data-theme="contact">
<a class="skip-link" href="#content">Skip to content</a>
<header class="panel">
{nav('contact.html')}
<section class="phero" id="content" tabindex="-1">
  <div class="fx">
    <p class="crumb"><a href="index.html">Our Little Village</a></p>
    <h1>Let's <em>talk.</em></h1>
    <p class="lede">We'd love to help you plan your next special event or sign your little one up for a class.</p>
    <div class="cta"><a class="btn main" href="#ways">Reach out</a><a class="btn alt" href="#visit">Come visit</a></div>
  </div>
  <div class="stage">
    <div class="arch"><video muted loop playsinline preload="none" poster="assets/work/parties.jpg" data-src="assets/work/parties.mp4" aria-hidden="true"></video></div>
    <img class="float" src="assets/work/balloons-a.jpg" alt="Two balloon columns in purple, black and pink">
  </div>
</section>
</header>
<main>
<section class="ways-wrap" id="ways"><h2 class="reveal">Pick what's <em>easiest.</em></h2><div class="tiles">{tiles}</div></section>
<section class="visit panel" id="visit"><div class="visit-in">
  <div class="stage">
    <div class="arch"><img loading="lazy" src="assets/slides/playroom.jpg" alt="The playroom at Our Little Village, with a painted sky mural, playhouse and green turf"></div>
    <img class="float" loading="lazy" src="assets/work/private-b.jpg" alt="Event room with pink tables and a draped ceiling">
  </div>
  <div class="reveal">
    <h2>Come see <em>the village.</em></h2>
    <address>1732 Victory Blvd<br>Staten Island, NY 10314</address>
    <p class="lede">Tour the playroom, the party room and everything in between.</p>
    <div class="cta"><a class="btn main" href="{MAPS}" target="_blank" rel="noopener">Get directions</a><a class="btn alt" href="{TEXT}">Text to book a tour</a></div>
  </div>
</div></section>
</main>
<footer><div><span>Our Little Village</span><span>1732 Victory Blvd, Staten Island, NY 10314</span><a href="{CALL}">Call 718-889-1374</a><a href="{TEXT}">Text 347-327-8166</a><a href="mailto:hello@ourlittlevillage.com">hello@ourlittlevillage.com</a><a href="privacy.html">Privacy Policy</a><span>&copy; 2026 Our Little Village LLC. All rights reserved.</span></div></footer>
<script src="assets/motion.js"></script>
<script src="assets/pages.js"></script>
</body>
</html>
"""


def privacy_page():
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy | Our Little Village, Staten Island</title>
<meta name="description" content="How Our Little Village handles information when you visit this website or register for a class.">
{share('privacy.html', 'Privacy Policy | Our Little Village', 'How Our Little Village handles information when you visit this website or register for a class.', 'home')}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<link rel="stylesheet" href="assets/pages.css">
<link rel="stylesheet" href="assets/access.css">
</head>
<body data-theme="privacy">
<a class="skip-link" href="#content">Skip to content</a>
<header class="panel">
{nav('privacy.html')}
<section class="phero plain">
  <div class="fx">
    <p class="crumb"><a href="index.html">Our Little Village</a></p>
    <h1>Privacy <em>policy.</em></h1>
    <p class="lede">What happens with your information when you visit this website.</p>
  </div>
</section>
</header>
<main class="legal" id="content" tabindex="-1">
  <h2>This website</h2>
  <p>You can browse this website without giving us any personal information. It has no accounts or sign-up forms, and it does not use advertising or analytics trackers.</p>
  <h2>Information you send us</h2>
  <p>If you call, text or email us, we use what you share to answer you and to plan your event or class.</p>
  <h2>Sharing your information</h2>
  <p>We do not sell your personal information.</p>
  <h2>Services we link to or use</h2>
  <ul>
    <li>Google Fonts displays the text on this website and receives your IP address when the page loads.</li>
    <li>Links to Google Maps and Instagram take you to those services, which have their own privacy policies.</li>
  </ul>
  <h2>Information saved in your browser</h2>
  <p>Your browser remembers whether you have already seen the opening video and whether you paused motion on the site. This stays on your device. This website does not set its own cookies.</p>
  <h2>Photos</h2>
  <p>If you see a photo of yourself or your child on this website and would like it removed, contact us and we will take care of it.</p>
  <h2>Your choices</h2>
  <p>To ask what information we have about you, or to ask us to correct or delete it, email <a href="mailto:hello@ourlittlevillage.com">hello@ourlittlevillage.com</a>. We may need to keep some records for legal or business reasons.</p>
  <h2>Contact</h2>
  <p>Our Little Village LLC, 1732 Victory Blvd, Staten Island, NY 10314<br><a href="mailto:hello@ourlittlevillage.com">hello@ourlittlevillage.com</a></p>
  <p class="updated">Last updated November 2026</p>
</main>
<footer><div><span>Our Little Village</span><span>1732 Victory Blvd, Staten Island, NY 10314</span><a href="{CALL}">Call 718-889-1374</a><a href="{TEXT}">Text 347-327-8166</a><a href="mailto:hello@ourlittlevillage.com">hello@ourlittlevillage.com</a><a href="privacy.html">Privacy Policy</a><span>&copy; 2026 Our Little Village LLC. All rights reserved.</span></div></footer>
<script src="assets/motion.js"></script>
<script src="assets/pages.js"></script>
</body>
</html>
"""


with open(os.path.join(SITE, "privacy.html"), "w") as f:
    f.write(privacy_page())
print("wrote privacy.html")

with open(os.path.join(SITE, "contact.html"), "w") as f:
    f.write(contact_page())
print("wrote contact.html")

PAGES = [to_page(load("pages/%s.json" % f[:-5]), f, clip) for f, clip in ORDER]
for i, p in enumerate(PAGES):
    with open(os.path.join(SITE, p["file"]), "w") as f:
        f.write(page(p, PAGES[(i + 1) % len(PAGES)]))
    print("wrote", p["file"])

home = os.path.join(SITE, "index.html")
with open(home) as f:
    s = f.read()
a, b = "<!-- cms:what-we-do", "  <!-- /cms:what-we-do -->"
start = s.index("\n", s.index(a)) + 1
s = s[:start] + what_we_do(load("home.json")) + s[s.index(b):]
with open(home, "w") as f:
    f.write(s)
print("wrote index.html (What we do)")
