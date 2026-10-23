"""
Sketchbook Buddy: a Discord bot built on the Art Toolkit.

Runs as a normal bot with no AI and no subscription needed.
Optional: add an ANTHROPIC_API_KEY to settings.env to switch on free-form AI chat
and sketchbook photo feedback. Everything else works without it.
"""
import asyncio
import base64
import datetime as dt
import json
import os
import random
import re
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import tasks

import content as C

HERE = Path(__file__).parent


# ------------------------------------------------------------------ settings
def load_settings():
    for name in ("settings.env", ".env"):
        p = HERE / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_settings()
TOKEN = os.getenv("DISCORD_TOKEN", "")
BOT_NAME = os.getenv("BOT_NAME", "Sketchbook Buddy")
DAILY_CHANNEL_ID = int(os.getenv("DAILY_CHANNEL_ID") or 0)
DAILY_HOUR = int(os.getenv("DAILY_HOUR") or 9)
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo(TIMEZONE)
except Exception:
    LOCAL_TZ = dt.timezone.utc


def today_local():
    return dt.datetime.now(LOCAL_TZ).date()


AI_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-haiku-5-5")
AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT") or 60)
AI_USERS = {int(x) for x in re.split(r"[,\s]+", os.getenv("AI_ALLOWED_USER_IDS", "")) if x.strip().isdigit()}

# ------------------------------------------------------------------ knowledge
K = json.loads((HERE / "knowledge.json").read_text(encoding="utf-8"))
THEMES = {t["name"].lower(): t for t in K["themes"]}
ARTISTS = {a["name"].lower(): a for a in K["artists"]}
PATHWAYS = ["Fine Art", "3D", "Graphic Communication", "Fashion/Textiles", "Photography"]

WORDS = {}  # term -> (definition, example)
for f in K["formal_elements"]:
    WORDS[f["word"].lower()] = (f["meaning"], f["example"])
for r in K["research_words"]:
    WORDS[r["word"].lower()] = (r["meaning"], "")
EXTRA_WORDS = {
    "impasto": "Paint put on thickly so brush or knife marks stand up from the surface.",
    "glazing": "Thin, see-through layers of paint built up on top of each other.",
    "sgraffito": "Scratching into a top layer to show the layer underneath.",
    "monoprint": "A print where you can only make one copy, often made by drawing onto an inked surface.",
    "collagraph": "A print made from a plate built up with textured materials like card, sand and glue.",
    "maquette": "A small test model of a 3D piece.",
    "armature": "The inner frame or skeleton that supports a sculpture.",
    "toile": "A test version of a garment, usually in cheap cotton.",
    "chiaroscuro": "Strong contrast between light and dark.",
    "juxtapose": "To put two different things side by side so they contrast.",
    "mark-making": "All the different lines, dots, scratches and textures you can make with a tool.",
    "hatching": "Shading with lots of parallel lines. Cross-hatching layers them in different directions.",
    "palette": "The set of colours an artist chooses to use.",
    "silhouette": "The outline shape of something, often filled in as one dark shape.",
    "abstract": "Art that doesn't try to show things realistically, focusing on shape, colour and mark instead.",
    "resolved": "When a piece feels finished and successfully answers what you set out to do.",
    "annotation": "The written notes next to your sketchbook work explaining what, how, why and what next.",
    "contextual": "About the story around a piece: when, where and why it was made.",
    "assemblage": "Art made by putting together found 3D objects.",
    "typography": "The design and arrangement of letters and text.",
}
for w, d in EXTRA_WORDS.items():
    WORDS.setdefault(w, (d, ""))

ART_VOCAB = set(WORDS) | {w.lower() for ws in K["describing_words"].values() for w in ws}
for v in K["technique_words"].values():
    ART_VOCAB |= {w.strip().lower() for w in re.split(r",|\(|\)", v) if 2 < len(w.strip()) < 25}
WEAK_WORDS = {
    "nice": "e.g. *calm, delicate, striking, harmonious*",
    "good": "say **what** is good about it, e.g. *the contrast works because...*",
    "cool": "e.g. *bold, dynamic, eye-catching, unsettling*",
    "messy": "e.g. *loose, gestural, expressive, layered*",
    "pretty": "e.g. *delicate, harmonious, vibrant, soft*",
    "bad": "say **what** didn't work and **why**",
    "weird": "e.g. *unsettling, unexpected, surreal, distorted*",
    "okay": "say what works and what you'd change",
    "stuff": "name the actual materials or objects",
    "things": "name the actual materials or objects",
    "like it": "add **because...**",
}

# ------------------------------------------------------------------ storage
DATA_DIR = Path(os.getenv("DATA_DIR") or HERE)
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "data.json"


def load_data():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"plans": {}, "ai_usage": {}}


DATA = load_data()
for _k in ("plans", "ai_usage", "briefs", "logs", "reminders_off", "game", "pings"):
    DATA.setdefault(_k, [] if _k == "reminders_off" else {})


def save_data():
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(DATA, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DATA_FILE)


# ------------------------------------------------------------------ helpers
ACKS = ["Nice. 👌", "Ooh, I like that.", "Good thinking.", "That's a really interesting angle.", "Love that.", "Okay, noted. ✍️"]
SESSION_TIMEOUT = 3 * 60 * 60
SESSIONS = {}  # (channel_id, user_id) -> dict


def chunks(text, size=1900):
    out, cur = [], ""
    for para in text.split("\n"):
        while len(para) > size:
            out.append(cur) if cur else None
            cur = ""
            out.append(para[:size]); para = para[size:]
        if len(cur) + len(para) + 1 > size:
            out.append(cur); cur = para
        else:
            cur = f"{cur}\n{para}" if cur else para
    if cur:
        out.append(cur)
    return [c for c in out if c.strip()]


async def send(channel, text, **kw):
    parts = chunks(text)
    for i, p in enumerate(parts):
        await channel.send(p, **(kw if i == len(parts) - 1 else {}))


def is_crisis(text):
    t = text.lower()
    return any(p in t for p in C.CRISIS_PHRASES)


BRIEF_MAP = {
    "home": "Place and Belonging", "belonging": "Place and Belonging", "landscape": "Place and Belonging",
    "self": "Identity", "self-portrait": "Identity", "who am i": "Identity", "portrait": "Identity", "culture": "Identity",
    "change": "Decay and Transformation", "transformation": "Decay and Transformation", "time": "Memory and Nostalgia",
    "nature": "Natural Forms", "growth": "Natural Forms", "plants": "Natural Forms", "environment": "Natural Forms",
    "architecture": "Structures and Architecture", "buildings": "Structures and Architecture", "urban": "The City",
    "past": "Memory and Nostalgia", "childhood": "Memory and Nostalgia", "nostalgia": "Memory and Nostalgia",
    "figure": "The Body", "human": "The Body", "movement": "Journeys and Movement", "travel": "Journeys and Movement",
    "conceal": "Hidden and Revealed", "secret": "Hidden and Revealed", "inside": "Hidden and Revealed", "layers": "Hidden and Revealed",
    "borders": "Boundaries and Barriers", "edges": "Boundaries and Barriers", "broken": "Fragments", "pieces": "Fragments",
    "darkness": "Light and Shadow", "light": "Light and Shadow", "repetition": "Pattern and Repetition",
    "sea": "Water and the Coast", "ocean": "Water and the Coast", "everyday": "Objects and Collections", "collection": "Objects and Collections",
}


def find(name, table):
    n = name.lower().strip()
    if n in table:
        return table[n]
    hits = [v for k, v in table.items() if n in k or k in n]
    return hits[0] if hits else None


async def theme_ac(inter, current):
    return [app_commands.Choice(name=t["name"], value=t["name"])
            for t in K["themes"] if current.lower() in t["name"].lower()][:25]


def artist_embed(a):
    e = discord.Embed(title=a["name"], description=a["meta"], colour=0xF27C38)
    e.add_field(name="Known for", value=a["known_for"], inline=False)
    e.add_field(name="Key work", value=a["key_work"].replace("<i>", "*").replace("</i>", "*"), inline=False)
    e.add_field(name="Borrow this", value=a["borrow"], inline=False)
    e.add_field(name="Themes", value=", ".join(a["themes"]), inline=True)
    e.add_field(name="Pathways", value=", ".join(a["pathways"]), inline=True)
    e.set_footer(text="Look up the key work, then try /study to write about it. 🟠 Part 6: Artists A to Z")
    return e


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


# ------------------------------------------------------------------ guided sessions
def new_session(kind, user_id, channel_id, **extra):
    s = {"kind": kind, "step": 0, "answers": [], "nudged": False, "ts": time.time(), **extra}
    SESSIONS[(channel_id, user_id)] = s
    return s


def end_session(channel_id, user_id):
    SESSIONS.pop((channel_id, user_id), None)


# ---- theme chat: 3 theme questions, each followed by one follow-up
def theme_prompt(s):
    t = THEMES[s["theme"].lower()]
    qs = s["questions"]
    i = s["step"]
    if i % 2 == 0:
        return f"**Question {i // 2 + 1} of {len(qs)}:** {qs[i // 2]}"
    return random.choice([f for f in C.FOLLOW_UPS if f not in s.get("used", [])] or C.FOLLOW_UPS)


def theme_wrap(s):
    t = THEMES[s["theme"].lower()]
    mind = "\n".join(f"• {a}" for a in s["answers"])
    arts = random.sample(t["artists"], min(2, len(t["artists"])))
    words = ", ".join(random.sample(t["words"], 6))
    return (
        f"## 🧠 Your mind map for **{t['name']}**\nEverything here came from **you**:\n{mind}\n\n"
        f"**Which one of these excites you most?** That's your starting point. Go with your gut.\n\n"
        f"**Words to play with:** {words}\n"
        f"**Two artists to look up:** " + " and ".join(f"**{a['name']}** ({strip_tags(a['note'])})" for a in arts) + "\n"
        f"**Primary research ideas:** {t['research']}\n"
        f"**Try a test:** {t['test']}\n\n"
        f"Next steps: `/artist` to read about those artists, `/spark` if you want a push, `/annotate` once you've made something. "
        f"Everything's also in the 🟢 Theme Idea Bank."
    )


# ---- annotate: What / How / Why / Next
ANNOTATE_Q = [
    ("WHAT", "**WHAT is it?** Describe the piece in a sentence.\n*e.g. \"This is a ... of ...\"*"),
    ("HOW", "**HOW did you make it?** Materials and technique.\n*e.g. \"I used ... by ...\"*"),
    ("WHY", "**WHY did you do it this way?** What were you going for, or what inspired it?\n*e.g. \"I wanted to ... because ...\"*"),
    ("NEXT", "**What did you learn, and what's NEXT?** What worked, what didn't, what you'll try.\n*e.g. \"This worked because... Next I'll try...\"*"),
]


def annotate_feedback(answers):
    text = " ".join(answers)
    low = text.lower()
    used = sorted({w for w in ART_VOCAB if re.search(rf"\b{re.escape(w)}\b", low)})
    weak = [(w, tip) for w, tip in WEAK_WORDS.items() if re.search(rf"\b{re.escape(w)}\b", low)]
    lines = ["## ✍️ Your annotation", "*All your own words, just put together:*", "> " + " ".join(a.rstrip() if a.rstrip()[-1:] in ".!?" else a.rstrip() + "." for a in answers), ""]
    if used:
        lines.append(f"✅ **Art words you used:** {', '.join(used[:10])}. Great.")
    if len(used) < 2:
        sample = random.sample([f["word"].lower() for f in K["formal_elements"]], 4)
        lines.append(f"💡 **Try adding 2 or 3 art words.** Could any of these fit? *{', '.join(sample)}* (more in 🟡 Art Words, or `/word`).")
    for w, tip in weak[:3]:
        lines.append(f"🔁 **\"{w}\"** could be stronger: {tip}")
    if "because" not in low:
        lines.append("💡 Add a **because** somewhere. It turns a description into a decision.")
    if len(answers[3].split()) < 6:
        lines.append("💡 Your **next step** is short. A specific next step shows planning, which is one of the 7 marking areas.")
    lines.append("\n**Marking areas this covers:** Context (what/why) · Developing practice (how) · Problem solving and Planning (next) · Evaluation (what worked).")
    lines.append("Copy it into your sketchbook, tweak anything that doesn't sound like you, and you're done. 🙌")
    return "\n".join(lines)


# ---- artist study: CFPM + opinion, link, response
STUDY_Q = [
    "**CONTENT**: What is the artwork? What's it of, or what do you think it's about?",
    "**FORM**: What do you notice about how it looks? Colours, lines, shapes, texture, composition?",
    "**PROCESS**: How do you think it was made? What materials and techniques?",
    "**MOOD**: How does it make you feel, and what in the work causes that?",
    "**YOUR OPINION**: What do you honestly think of it, and why? (It's fine not to like it.)",
    "**THE LINK**: How does it connect to your theme or your own work?",
    "**YOUR RESPONSE**: What could you make in response? A study, a technique test, or changing one thing like scale or material?",
]
STUDY_LABELS = ["Content", "Form", "Process", "Mood", "My opinion", "Link to my work", "My response"]


def study_wrap(s):
    a = s.get("artist") or "the artist"
    body = "\n".join(f"**{lab}:** {ans}" for lab, ans in zip(STUDY_LABELS, s["answers"]))
    return (f"## 🔵 Your artist page notes: {a}\n{body}\n\n"
            "**Don't forget:** a title (name, dates, what they do), 1 to 3 labelled images, and then **actually make** your response piece. "
            "That's where the marks are. Use the 🔵 Writing About Artists guide for the full recipe.")


# ---- plan
def plan_text(uid):
    p = DATA["plans"].get(str(uid))
    if not p or not p["tasks"]:
        return "You don't have a plan yet. Use `/plan` to make one."
    days = {}
    for i, t in enumerate(p["tasks"], 1):
        days.setdefault(t["day"], []).append((i, t))
    out = ["## 📋 Your plan"]
    for d in sorted(days):
        out.append(f"**Day {d}**")
        for i, t in days[d]:
            out.append(f"{'✅' if t['done'] else '⬜'} `{i}` {'~~' + t['text'] + '~~' if t['done'] else t['text']}")
    done = sum(t["done"] for t in p["tasks"])
    out.append(f"\n{done}/{len(p['tasks'])} done. Tick one off with `/done number`.")
    return "\n".join(out)


async def handle_session(msg, s):
    text = msg.content.strip()
    low = text.lower()
    ch, uid = msg.channel.id, msg.author.id
    s["ts"] = time.time()
    if low in ("stop", "cancel", "quit", "end", "exit"):
        end_session(ch, uid)
        return await msg.channel.send("No worries, stopped. Pick it up any time. 🙂")
    skip = low in ("skip", "pass", "idk", "i don't know", "i dont know", "dunno")

    kind = s["kind"]
    if kind == "theme":
        if not skip and len(text.split()) < 3 and not s["nudged"] and s["step"] % 2 == 0:
            s["nudged"] = True
            return await msg.channel.send(random.choice(C.SHORT_ANSWER_NUDGES))
        if not skip:
            s["answers"].append(text)
        s["nudged"] = False
        s["step"] += 2 if (skip and s["step"] % 2 == 0) else 1
        if s["step"] >= len(s["questions"]) * 2:
            end_session(ch, uid)
            return await send(msg.channel, theme_wrap(s) if s["answers"] else
                              "That's okay, sometimes it doesn't click straight away. Try `/challenge` to warm up, then come back to `/theme`.")
        nxt = theme_prompt(s)
        s.setdefault("used", []).append(nxt)
        if skip:
            return await msg.channel.send(f"That's fine, let's try another angle.\n\n{nxt}")
        if s["step"] % 2 == 0:
            return await msg.channel.send(f"{random.choice(ACKS)}\n\n{nxt}")
        return await msg.channel.send(nxt)

    if kind == "annotate":
        if skip:
            return await msg.channel.send("Have a go, even half a sentence. You can edit it after. If you're stuck, use the example as a template.")
        s["answers"].append(text)
        s["step"] += 1
        if s["step"] >= len(ANNOTATE_Q):
            end_session(ch, uid)
            return await send(msg.channel, annotate_feedback(s["answers"]))
        return await msg.channel.send(f"{random.choice(ACKS)}\n\n{ANNOTATE_Q[s['step']][1]}")

    if kind == "study":
        if s["step"] == -1:
            a = find(text, ARTISTS)
            s["artist"] = a["name"] if a else text
            s["step"] = 0
            if a:
                await msg.channel.send("Found them in the A to Z:", embed=artist_embed(a))
            await msg.channel.send(f"Pick **one** of their works and have it open in front of you. Got it? Let's go.\n\n{STUDY_Q[0]}")
            return
        s["answers"].append(text if not skip else "(come back to this)")
        s["step"] += 1
        if s["step"] >= len(STUDY_Q):
            end_session(ch, uid)
            return await send(msg.channel, study_wrap(s))
        return await msg.channel.send(f"{random.choice(ACKS)}\n\n{STUDY_Q[s['step']]}")

    if kind == "describe":
        img = next((a for a in msg.attachments if (a.content_type or "").startswith("image/")), None)
        if not img and len(text.split()) < 4:
            return await msg.channel.send("Send a photo, or describe your piece in a sentence or two (what it is, what you used, what it looks like).")
        end_session(ch, uid)
        return await run_describe(msg.channel, uid, img, text)

    if kind == "plan":
        if s["step"] == 0:
            items = [i.strip(" -•*\t") for i in re.split(r"\n|;|,(?![^()]*\))", text) if i.strip(" -•*\t")]
            if not items:
                return await msg.channel.send("I didn't catch any tasks. List them one per line, or separated by commas.")
            s["items"] = items[:40]
            s["step"] = 1
            return await msg.channel.send(f"Got **{len(s['items'])}** tasks. Over how many **days** do you want to spread them? (Just type a number, e.g. `7`)")
        if s["step"] == 1:
            m = re.search(r"\d+", text)
            if not m:
                return await msg.channel.send("Just a number please, like `5`.")
            days = max(1, min(60, int(m.group())))
            items = s["items"]
            per = -(-len(items) // days)
            DATA["plans"][str(uid)] = {"tasks": [{"text": t, "day": i // per + 1, "done": False} for i, t in enumerate(items)],
                                       "made": dt.date.today().isoformat()}
            save_data()
            end_session(ch, uid)
            return await send(msg.channel, plan_text(uid) + "\n\nOnly look at **today's** tasks. The rest can wait. 💪")


# ------------------------------------------------------------------ free-text replies (no AI)
def keyword_reply(text):
    low = text.lower()
    if re.search(r"\b(hi|hey|hello|yo|hiya)\b", low) and len(low) < 25:
        return C.WELCOME
    for name, t in THEMES.items():
        short = name.split(" and ")[0].replace("the ", "")
        if short in low:
            return (f"**{t['name']}**: {t['meaning']}\n\nWant to explore it together? Try `/theme {t['name']}` "
                    f"and I'll ask you some questions to get your ideas flowing.")
    for name, a in ARTISTS.items():
        last = name.split()[-1]
        if name in low or (len(last) > 4 and re.search(rf"\b{re.escape(last)}\b", low)):
            return f"**{a['name']}** ({a['meta']}): {a['known_for']}\nUse `/artist {a['name']}` for the full card, or `/study` to write about them."
    asking = re.search(r"\b(what|whats|meaning|mean|means|define|definition|explain)\b", low)
    for w, (d, ex) in WORDS.items():
        if asking and re.search(rf"\b{re.escape(w)}\b", low):
            return f"**{w.title()}**: {d}" + (f"\n*Use it like this: {ex}*" if ex else "")
    if any(k in low for k in ("overwhelm", "stress", "panic", "anxious", "behind", "can't do", "cant do", "too much", "give up")):
        return ("That sounds like a lot. You're not on your own with it. 🤍\n\n"
                "Try `/stuck` and pick what's going on, or `/checkin`. `/plan` can split your work into small daily chunks. "
                "And your tutor genuinely wants to help, so it's okay to ask them.")
    if "annotat" in low or "what do i write" in low or "what to write" in low:
        return "Try `/annotate`: I'll ask you What, How, Why and Next one at a time, then put your answers together and suggest stronger words."
    if "idea" in low or "inspir" in low or "what should i make" in low or "what to make" in low:
        return "Ideas come from research and asking good questions. Try `/theme` for a guided chat, or `/spark` for a creative push. I won't hand you ideas, but I'll help yours show up. ✨"
    if "artist" in low:
        return "Try `/artists` to list artists by theme or pathway, `/artist` for one artist's card, or `/study` to write an artist page step by step."
    if any(k in low for k in ("plan", "deadline", "schedule", "organis", "organiz", "to do", "todo")):
        return "Try `/plan` and give me your list. I'll spread it over days. Then `/todo` shows it and `/done` ticks things off."
    if any(k in low for k in ("mark", "grade", "assess", "criteria", "pass", "merit", "distinction")):
        areas = "\n".join(f"• **{m['area']}**: {m['plain']}" for m in K["marking_areas"])
        return f"Foundation is marked on 7 areas:\n{areas}\n\nThe 🩷 How to Annotate guide explains each one."
    if any(k in low for k in ("thank", "ty", "cheers")):
        return "Any time! 🙌"
    return ("I'm a simple bot, so I work best with commands. Type `/` to see them all, or `/help`.\n"
            "Popular ones: `/theme` · `/annotate` · `/spark` · `/stuck` · `/artist`")


# ------------------------------------------------------------------ optional AI
AI = None
HISTORY = {}  # channel_id -> list of messages
if AI_KEY:
    try:
        from anthropic import AsyncAnthropic
        AI = AsyncAnthropic(api_key=AI_KEY)
    except ImportError:
        print("ANTHROPIC_API_KEY is set but the 'anthropic' package isn't installed. AI mode is off.")

SYSTEM_PROMPT = f"""You are {BOT_NAME}, a Discord study buddy for an art student on a UK Level 3 Foundation Diploma in Art and Design (UAL). \
They are in the early exploratory stage and haven't chosen a pathway yet. They can feel overwhelmed, get information overload, \
compare themselves to classmates and find it hard to ask for help.

YOUR MOST IMPORTANT RULE: never hand them ideas, concepts, compositions or finished annotation text. Their ideas must come from them.
- Facts are fine to give freely: art vocabulary, techniques, artist information, how the course is marked, how to structure things.
- Creative decisions are theirs: answer with questions, reflect their own words back, offer "what if" provocations, constraints and exercises.
- If they ask "what should I make?", ask about their research and what has caught their eye, then give 2 or 3 open questions or a short exercise.
- If they share writing, give feedback and ask questions so they improve it themselves. Don't rewrite it for them.
- If they share a sketchbook photo: name specifically what's working using art vocabulary, ask one or two questions, and suggest one experiment.

STYLE: warm, calm and encouraging, and honest. Hype them up properly when they make progress. Keep replies short for Discord: \
usually under 120 words, one or two questions at a time, no walls of text. Simple language but proper art terms, briefly explained. \
UK spelling. Light emoji only.

TOOLKIT: they have 7 colour-coded PDFs. Point them to the right one when useful: 🟡 Part 1 Art Words, 🩷 Part 2 How to Annotate, \
🔵 Part 3 Writing About Artists (CFPM), 🟢 Part 4 Theme Idea Bank, 🟣 Part 5 Links, 🟠 Part 6 Artists A to Z, 🩵 Part 7 References. \
Bot commands they can use: /theme /annotate /study /spark /challenge /stuck /checkin /plan /todo /artist /artists /word /hype.

SUPPORT: normalise struggle, break things into tiny steps, celebrate small wins. Encourage them to talk to their tutor, friends and family. \
You support them, but you don't replace real people. If they mention self-harm, suicide or being in danger, respond with care and give UK \
support: Samaritans 116 123 (24/7), text SHOUT to 85258, or 999 in an emergency, and encourage them to tell someone they trust.

ACCURACY: if you're not sure about a fact (especially artist dates or works), say so and suggest checking Tate or The Art Story.

KNOWLEDGE (the toolkit):
"""


def knowledge_text():
    parts = []
    parts.append("MARKING AREAS: " + "; ".join(f"{m['area']}: {m['plain']}" for m in K["marking_areas"]))
    parts.append("STAGES: " + "; ".join(f"{s['stage']}: {s['what']} ({s['graded']})" for s in K["stages"]))
    parts.append("FORMAL ELEMENTS: " + "; ".join(f"{f['word']}: {f['meaning']}" for f in K["formal_elements"]))
    parts.append("DESCRIBING WORDS: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in K["describing_words"].items()))
    parts.append("TECHNIQUE WORDS: " + "; ".join(f"{k}: {v}" for k, v in K["technique_words"].items()))
    parts.append("CFPM: " + "; ".join(f"{c['heading']}: {c['questions']}" for c in K["cfpm"]))
    for t in K["themes"]:
        parts.append(f"THEME {t['name']}: {t['meaning']} Questions: {' / '.join(t['questions'])} Words: {', '.join(t['words'])}. "
                     f"Artists: {', '.join(strip_tags(a['name']) for a in t['artists'])}.")
    parts.append("ARTISTS: " + " | ".join(f"{a['name']} ({a['meta']}): {a['known_for']} Key work: {strip_tags(a['key_work'])}"
                                         for a in K["artists"]))
    return "\n".join(parts)


AI_SYSTEM = [{"type": "text", "text": SYSTEM_PROMPT + knowledge_text(), "cache_control": {"type": "ephemeral"}}]


def ai_system(uid, extra=""):
    blocks = list(AI_SYSTEM)
    brief = DATA["briefs"].get(str(uid))
    note = (f"Their current project brief/theme: {brief}\n" if brief else "") + extra
    if note:
        blocks.append({"type": "text", "text": note})
    return blocks


def ai_allowed(uid):
    if not AI:
        return False
    if AI_USERS and uid not in AI_USERS:
        return False
    today = dt.date.today().isoformat()
    u = DATA.setdefault("ai_usage", {})
    if u.get("date") != today:
        u.clear(); u["date"] = today; u["count"] = 0
    return u["count"] < AI_DAILY_LIMIT


async def ai_reply(msg, text):
    blocks = []
    for att in msg.attachments[:3]:
        ctype = (att.content_type or "").split(";")[0]
        if ctype.startswith("image/") and ctype not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            return await msg.channel.send("I can't open that photo format. Could you send it as a screenshot or a JPG/PNG? 📸")
        if ctype in ("image/jpeg", "image/png", "image/gif", "image/webp") and att.size < 4_500_000:
            data = base64.b64encode(await att.read()).decode()
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": att.content_type.split(";")[0], "data": data}})
    blocks.append({"type": "text", "text": text or "Here's a page from my sketchbook. What do you think?"})
    DATA["ai_usage"]["count"] = DATA["ai_usage"].get("count", 0) + 1
    save_data()
    hist = HISTORY.setdefault(msg.channel.id, [])
    hist.append({"role": "user", "content": blocks})
    del hist[:-16]
    while hist and hist[0]["role"] != "user":
        hist.pop(0)
    try:
        async with msg.channel.typing():
            r = await AI.messages.create(model=AI_MODEL, max_tokens=700, system=ai_system(msg.author.id), messages=hist)
        out = "".join(b.text for b in r.content if b.type == "text").strip()
    except Exception as e:
        print("AI error:", e)
        hist.pop()
        return await msg.channel.send("My AI brain is having a moment. 😅 Commands still work, so try `/help`.")
    # keep text only in history to save cost (drop image data after first reply)
    hist[-1] = {"role": "user", "content": [b if b["type"] == "text" else {"type": "text", "text": "[sketchbook photo]"} for b in blocks]}
    hist.append({"role": "assistant", "content": out})
    await send(msg.channel, out)


# ------------------------------------------------------------------ /describe and /ask helpers
IMG_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")
NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
RING_COLOURS = ["#F2B705", "#EE5A8C", "#3D8BFD", "#34B36B", "#9B6BF2"]

DESCRIBE_PROMPT = """Look at this art student's sketchbook work. Your job is to help them find WORDS to describe it in their \
own annotations. They will write the sentences themselves.
Rules:
- Give single words or short art terms only. NEVER full sentences they could copy.
- Be specific to what you can actually see. Be warm and encouraging. Don't grade or judge quality.
- Use proper art vocabulary (formal elements, techniques) at UK Level 3 Foundation level.
Return ONLY valid JSON in this exact shape:
{"regions": [{"x": 0-100, "y": 0-100, "r": 6-30, "see": "max 6 words, e.g. intense dark shading", \
"element": "Line|Tone|Colour|Texture|Shape|Form|Space|Pattern|Composition|Technique", "words": ["4 to 6 words"]}],
 "overall": {"Mood": ["3-5 words"], "Composition": ["3-5 words"], "Technique": ["3-5 words"]},
 "questions": ["2 short questions that make them think about WHY they made their choices"]}
Give 2 to 5 regions. x and y are the centre of the region as a percentage of image width and height; \
r is the radius as a percentage of image width. If there is no image (only a written description), return an empty regions list."""

ASK_NOTE = ("They used /ask with a question about their course, art, or a topic. Answer clearly and accurately, like a kind tutor. "
            "Keep it under 150 words, use simple language with proper art terms explained, and point to the right toolkit part or command if useful. "
            "Facts and explanations are fine. If the question asks you to make creative decisions or write their work for them, "
            "guide them with questions instead.")


def parse_json(text):
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:
        return None


def draw_rings(img_bytes, regions):
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    im = ImageOps.exif_transpose(Image.open(BytesIO(img_bytes))).convert("RGB")
    im.thumbnail((1600, 1600))
    W_, H_ = im.size
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(18, W_ // 30))
    except Exception:
        try:
            font = ImageFont.load_default(size=max(18, W_ // 30))
        except TypeError:
            font = ImageFont.load_default()
    lw = max(4, W_ // 200)
    for i, rg in enumerate(regions[:5]):
        try:
            x, y = float(rg["x"]) / 100 * W_, float(rg["y"]) / 100 * H_
            r = max(20, min(float(rg.get("r", 12)), 35) / 100 * W_)
        except Exception:
            continue
        col = RING_COLOURS[i % 5]
        d.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2], outline="white", width=lw + 4)
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=lw)
        br = max(16, W_ // 40)
        bx, by = min(max(x - r * 0.72, br), W_ - br), min(max(y - r * 0.72, br), H_ - br)
        d.ellipse([bx - br, by - br, bx + br, by + br], fill=col, outline="white", width=3)
        d.text((bx, by), str(i + 1), fill="white", font=font, anchor="mm")
    out = BytesIO()
    im.save(out, "JPEG", quality=88)
    out.seek(0)
    return out


def describe_text(data, has_image):
    lines = ["## 🔍 Words for your work", "*Words only. The sentences are yours to write.* ✍️", ""]
    for i, rg in enumerate((data.get("regions") or [])[:5]):
        words = " · ".join(rg.get("words", [])[:6])
        tag = f" ({rg['element']})" if rg.get("element") else ""
        lines.append(f"{NUMS[i]} *{rg.get('see', '')}*{tag}\n→ {words}")
    ov = data.get("overall") or {}
    if ov:
        lines.append("\n**Overall**")
        for k, v in ov.items():
            if v:
                lines.append(f"**{k}:** {' · '.join(v[:5])}")
    qs = data.get("questions") or []
    if qs:
        lines.append("\n**Think about:**\n" + "\n".join(f"• {q}" for q in qs[:2]))
    lines.append("\n**Your turn:** pick 2 or 3 words " + ("from each number " if has_image else "") +
                 "and write your **own** sentences. Stuck on how? `/annotate` walks you through it.")
    return "\n".join(lines)


async def run_describe(channel, uid, img_att=None, text=""):
    """AI describe. img_att = discord.Attachment or None. Returns nothing; posts to channel."""
    content, img_bytes = [], None
    if img_att is not None:
        ctype = (img_att.content_type or "").split(";")[0]
        if ctype not in IMG_TYPES or img_att.size > 4_500_000:
            return await channel.send("I can't open that one. Could you send a screenshot or a JPG/PNG under 4MB? 📸")
        img_bytes = await img_att.read()
        content.append({"type": "image", "source": {"type": "base64", "media_type": ctype,
                                                     "data": base64.b64encode(img_bytes).decode()}})
    content.append({"type": "text", "text": (f"Student's description: {text}" if text else "Here's my work.")})
    DATA["ai_usage"]["count"] = DATA["ai_usage"].get("count", 0) + 1
    save_data()
    try:
        async with channel.typing():
            r = await AI.messages.create(model=AI_MODEL, max_tokens=900, system=ai_system(uid, DESCRIBE_PROMPT),
                                         messages=[{"role": "user", "content": content}])
        data = parse_json("".join(b.text for b in r.content if b.type == "text"))
    except Exception as e:
        print("AI describe error:", e)
        data = None
    if not data:
        return await channel.send("I couldn't read that one properly. 😅 Try again, or use `/describe` without a photo for the guided version.")
    file = None
    if img_bytes and data.get("regions"):
        try:
            file = discord.File(draw_rings(img_bytes, data["regions"]), filename="your_work_marked.jpg")
        except Exception as e:
            print("draw error:", e)
    text_out = describe_text(data, bool(file))
    parts = chunks(text_out)
    await channel.send(parts[0], file=file) if file else await channel.send(parts[0])
    for p in parts[1:]:
        await channel.send(p)


def guided_describe_text(keys):
    out = ["## 🔍 Words for your work", "*Look at your piece, then pick the words that honestly match what you see.*", ""]
    labels = {k: (lab, emo) for k, lab, emo in C.DESCRIBE_OPTIONS}
    for k in keys:
        lab, emo = labels[k]
        if k == "materials":
            words = ", ".join(re.sub(r"\([^)]*\)", "", v) for v in K["technique_words"].values())
            words = " · ".join(dict.fromkeys(w.strip() for w in re.split(r",|\(|\)", words) if 2 < len(w.strip()) < 22))
            words = " · ".join(words.split(" · ")[:24])
        else:
            src = {"tone": "Tone", "line": "Line", "colour": "Colour", "texture": "Texture",
                   "composition": "Composition", "mood": "Mood"}.get(k)
            base = list(K["describing_words"].get(src, [])) if src else []
            words = " · ".join(base + C.DESCRIBE_EXTRA.get(k, []))
        qs = "\n".join(f"  ↳ {q}" for q in C.LOOK_Q[k])
        out.append(f"{emo} **{lab}**\n{words}\n{qs}\n")
    out.append("**Your turn:** choose 2 or 3 words and write your **own** sentence. Need a structure? `/annotate` helps.")
    return "\n".join(out)


class DescribeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)
        sel = discord.ui.Select(placeholder="What can you see in your work? Pick all that apply",
                                min_values=1, max_values=len(C.DESCRIBE_OPTIONS),
                                options=[discord.SelectOption(label=lab, value=k, emoji=emo) for k, lab, emo in C.DESCRIBE_OPTIONS])
        sel.callback = self.picked
        self.sel = sel
        self.add_item(sel)

    async def picked(self, inter: discord.Interaction):
        order = [k for k, _, _ in C.DESCRIBE_OPTIONS if k in self.sel.values]
        parts = chunks(guided_describe_text(order))
        await inter.response.send_message(parts[0])
        for p in parts[1:]:
            await inter.followup.send(p)


# ---- Sketchbook Quest: points, streaks, levels
def player(uid):
    return DATA["game"].setdefault(str(uid), {"points": 0, "days": {}, "best": 0, "settled": None})


def done_dates(uid):
    g = DATA["game"].get(str(uid), {"days": {}})
    s = {d for d, v in g["days"].items() if v in ("yes", "caught")}
    s |= {e["date"] for e in DATA["logs"].get(str(uid), [])}
    return s


def streak(uid):
    days = done_dates(uid)
    cur = today_local()
    if cur.isoformat() not in days:
        cur -= dt.timedelta(days=1)          # today not done yet: streak still alive from yesterday
    n = 0
    while cur.isoformat() in days:
        n += 1; cur -= dt.timedelta(days=1)
    return n


def level(points):
    title, nxt = C.LEVELS[0][1], None
    for i, (need, name) in enumerate(C.LEVELS):
        if points >= need:
            title = name
            nxt = C.LEVELS[i + 1] if i + 1 < len(C.LEVELS) else None
    return title, nxt


def settle(uid):
    """Turn unanswered past days (since the ping was set up) into misses. Returns list of missed dates."""
    g = player(uid)
    ping = DATA["pings"].get(str(uid))
    if not ping:
        return []
    start = dt.date.fromisoformat(g["settled"] or ping["since"])
    yesterday = today_local() - dt.timedelta(days=1)
    missed, d = [], max(start, yesterday - dt.timedelta(days=6))   # never punish more than 7 days at once
    logs = {e["date"] for e in DATA["logs"].get(str(uid), [])}
    while d <= yesterday:
        k = d.isoformat()
        if k not in g["days"] and k >= ping["since"]:
            if k in logs:
                g["days"][k] = "yes"; g["points"] += C.POINTS_YES
            else:
                g["days"][k] = "miss"; g["points"] += C.POINTS_MISS; missed.append(k)
        d += dt.timedelta(days=1)
    g["settled"] = (yesterday + dt.timedelta(days=1)).isoformat()
    save_data()
    return missed


def catchable(uid):
    g = player(uid)
    t = today_local()
    return sorted((d for d, v in g["days"].items() if v in ("no", "miss")
                   and 1 <= (t - dt.date.fromisoformat(d)).days <= C.CATCHUP_DAYS), reverse=True)


def mark_yes(uid, day=None):
    """Record a sketchbook day. Returns (points_gained, streak, bonus) or None if already counted."""
    g = player(uid)
    k = (day or today_local()).isoformat()
    if g["days"].get(k) in ("yes", "caught"):
        return None
    prev = g["days"].get(k)
    gained = C.POINTS_YES - (C.POINTS_NO if prev == "no" else 0)
    g["days"][k] = "yes"
    n = streak(uid)
    bonus = C.STREAK_BONUS if n and n % 7 == 0 else 0
    g["points"] += gained + bonus
    g["best"] = max(g.get("best", 0), n)
    save_data()
    return gained + bonus, n, bonus


def score_line(uid):
    g = player(uid)
    title, nxt = level(g["points"])
    to_next = f" · {nxt[0] - g['points']} to {nxt[1]}" if nxt else ""
    return f"🔥 **{streak(uid)}-day streak** · ⭐ **{g['points']} pts** · {title}{to_next}"


class QuestButton(discord.ui.DynamicItem[discord.ui.Button], template=r"sq:(?P<act>yes|no|catch):(?P<uid>\d+)"):
    def __init__(self, act, uid):
        labels = {"yes": ("✅ Yes, I did it!", discord.ButtonStyle.success),
                  "no": ("❌ Not today", discord.ButtonStyle.danger),
                  "catch": ("🔁 I did extra to catch up", discord.ButtonStyle.primary)}
        lab, style = labels[act]
        super().__init__(discord.ui.Button(label=lab, style=style, custom_id=f"sq:{act}:{uid}"))
        self.act, self.uid = act, int(uid)

    @classmethod
    async def from_custom_id(cls, inter, item, match):
        return cls(match["act"], match["uid"])

    async def callback(self, inter: discord.Interaction):
        if inter.user.id != self.uid:
            return await inter.response.send_message("This button isn't yours. 👀 Use `/ping` to set up your own!", ephemeral=True)
        await inter.response.send_message(quest_answer(self.uid, self.act))


def quest_answer(uid, act):
    settle(uid)
    g = player(uid)
    k = today_local().isoformat()
    if act == "yes":
        r = mark_yes(uid)
        if not r:
            return f"Already counted today. ✅ Go rest, legend.\n{score_line(uid)}"
        gained, n, bonus = r
        extra = f"\n🎉 **{n} DAYS IN A ROW! +{bonus} bonus!**" if bonus else ""
        return f"{random.choice(C.YES_LINES)} **+{gained - bonus} ⭐**{extra}\n{score_line(uid)}"
    if act == "no":
        if g["days"].get(k) in ("yes", "caught"):
            return f"Wait, you already said yes today! Keeping that. ✅\n{score_line(uid)}"
        if g["days"].get(k) == "no":
            return f"Already noted. Tomorrow's a new page. 🌅\n{score_line(uid)}"
        g["days"][k] = "no"; g["points"] += C.POINTS_NO; save_data()
        return (f"{random.choice(C.NO_LINES)} **{C.POINTS_NO} ⭐**\n{score_line(uid)}\n"
                f"*Win it back: do a double session in the next {C.CATCHUP_DAYS} days and tap 🔁 catch up (or use `/sketched catch up`).*")
    # catch up
    days = catchable(uid)
    if not days:
        return f"Nothing to catch up on, you're all square! 🙌\n{score_line(uid)}"
    d = days[0]
    lost = C.POINTS_MISS if g["days"][d] == "miss" else C.POINTS_NO
    g["days"][d] = "caught"
    g["points"] += -lost + C.POINTS_CATCHUP
    g["best"] = max(g.get("best", 0), streak(uid))
    save_data()
    return f"{random.choice(C.CATCHUP_LINES)} **+{-lost + C.POINTS_CATCHUP} ⭐** ({d})\n{score_line(uid)}"


def quest_view(uid):
    v = discord.ui.View(timeout=None)
    v.add_item(QuestButton("yes", uid)); v.add_item(QuestButton("no", uid))
    if catchable(uid):
        v.add_item(QuestButton("catch", uid))
    return v


async def send_ping(uid, ping):
    ch = bot.get_channel(ping["channel"]) or await bot.fetch_channel(ping["channel"])
    missed = settle(int(uid))
    lines = [f"<@{uid}> {ping.get('message') or C.DEFAULT_PING}"]
    if missed:
        lines.append(f"{random.choice(C.MISS_LINES)} **{C.POINTS_MISS * len(missed)} ⭐**"
                     + (" Tap 🔁 after a double session to win it back." if catchable(int(uid)) else ""))
    if today_local().isoformat() in done_dates(int(uid)):
        lines.append("…oh wait, you already did it today. 😌 Nice.")
    lines.append(score_line(int(uid)))
    lines.append("**Did you do sketchbook today?**")
    await ch.send("\n".join(lines), view=quest_view(int(uid)),
                  allowed_mentions=discord.AllowedMentions(users=True))


def today_tasks(uid):
    p = DATA["plans"].get(str(uid))
    if not p or not p.get("tasks"):
        return []
    made = dt.date.fromisoformat(p.get("made", dt.date.today().isoformat()))
    day = (dt.date.today() - made).days + 1
    return [(i, t) for i, t in enumerate(p["tasks"], 1) if not t["done"] and t["day"] <= day]


# ------------------------------------------------------------------ discord client
intents = discord.Intents.default()
intents.message_content = True


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_dynamic_items(QuestButton)
        await self.tree.sync()
        daily_post.start()
        ping_loop.start()


bot = Bot()
tree = bot.tree


@bot.event
async def on_ready():
    print(f"{BOT_NAME} is online as {bot.user} | AI mode: {'ON (' + AI_MODEL + ')' if AI else 'off'}")


@bot.event
async def on_message(msg: discord.Message):
    if msg.author.bot:
        return
    text = msg.content
    if bot.user:
        text = text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    key = (msg.channel.id, msg.author.id)
    s = SESSIONS.get(key)
    if s and time.time() - s["ts"] > SESSION_TIMEOUT:
        end_session(*key); s = None

    is_dm = isinstance(msg.channel, discord.DMChannel)
    mentioned = bot.user in msg.mentions if bot.user else False
    replying = bool(msg.reference and msg.reference.resolved and getattr(msg.reference.resolved, "author", None) == bot.user)
    if not (s or is_dm or mentioned or replying):
        return

    if is_crisis(text):
        if s:
            end_session(*key)
        return await msg.channel.send(C.CRISIS_REPLY)
    if s:
        return await handle_session(msg, s)
    if ai_allowed(msg.author.id):
        return await ai_reply(msg, text)
    if msg.attachments and not text:
        return await msg.channel.send("I can't see pictures on my own, but try `/describe`: tell me what's in your work and I'll give you words to write about it. 🔍")
    await send(msg.channel, keyword_reply(text))


async def start_in_channel(inter: discord.Interaction, kind, opener, **extra):
    new_session(kind, inter.user.id, inter.channel_id, **extra)
    await inter.response.send_message(opener + "\n\n*Type your answer as a normal message. `skip` to skip a question, `stop` to finish early.*")


# ------------------------------------------------------------------ slash commands
@tree.command(name="help", description="What I can do")
async def help_cmd(inter: discord.Interaction):
    e = discord.Embed(title=f"🎨 {BOT_NAME}", colour=0x34B36B,
                      description="I help you **think**, not think for you. Your ideas are what make your work yours.")
    e.add_field(name="💭 Ideas", value="`/theme`: guided chat about a theme\n`/spark`: a creative push\n`/challenge`: quick sketchbook warm-up", inline=False)
    e.add_field(name="✍️ Writing", value="`/describe`: get **words** for your work" + (" (send a photo!)" if AI else "") +
                "\n`/annotate`: build an annotation from your answers\n`/study`: write an artist page step by step\n`/word`: what does this art word mean?", inline=False)
    e.add_field(name="❓ Questions", value="`/ask`: ask anything about your course, art or a topic", inline=False)
    e.add_field(name="🖼️ Artists", value="`/artist`: one artist's card\n`/artists`: list by theme or pathway", inline=False)
    e.add_field(name="📋 Organising", value="`/brief`: save your current brief\n`/plan`: split your work into days\n`/todo`: see your plan · `/done`: tick something off\n"
                "`/log`: log what you did (build a streak!)\n`/progress`: see how far you've come", inline=False)
    e.add_field(name="🎮 Sketchbook game", value="`/ping`: daily reminder at your time, tagged with your name\n"
                "`/sketched`: did you do it today? (points!)\n`/score`: streak, points and level · `/leaderboard`: who's winning", inline=False)
    e.add_field(name="🤍 Support", value="`/checkin`: how are you doing?\n`/stuck`: get unstuck\n`/hype`: a little boost", inline=False)
    if AI:
        e.add_field(name="💬 Chat", value="@mention me or DM me to chat. You can send sketchbook photos too.", inline=False)
    e.set_footer(text="Type stop any time to end a guided chat. /reset if I get confused.")
    await inter.response.send_message(embed=e)


@tree.command(name="theme", description="Explore a theme together. I'll ask questions to get your ideas going")
@app_commands.describe(theme="Pick a theme (or type your brief's theme)")
async def theme_cmd(inter: discord.Interaction, theme: str):
    t = find(theme, THEMES)
    mapped = ""
    if not t and theme.lower().strip() in BRIEF_MAP:
        t = THEMES[BRIEF_MAP[theme.lower().strip()].lower()]
        mapped = f"*\"{theme}\" fits nicely with* ***{t['name']}***, *so let's use that.*\n\n"
    if not t:
        names = ", ".join(x["name"] for x in K["themes"])
        return await inter.response.send_message(
            f"I don't have **{theme}** in my bank yet. Pick the closest one: {names}.\n"
            f"Tip: most briefs fit one of these, e.g. *\"Home\"* → Place and Belonging, *\"Change\"* → Decay and Transformation.")
    qs = random.sample(t["questions"], 3)
    await start_in_channel(inter, "theme",
                           f"{mapped}## 🟢 {t['name']}\n{t['meaning']}\n\nI'll ask you **3 questions**, plus a little follow-up for each. "
                           f"There are no wrong answers, and weird ones are often the best.\n\n**Question 1 of 3:** {qs[0]}",
                           theme=t["name"], questions=qs)


theme_cmd.autocomplete("theme")(theme_ac)


@tree.command(name="themes", description="List all 16 themes")
async def themes_cmd(inter: discord.Interaction):
    lines = "\n".join(f"`{i}` **{t['name']}**: {t['meaning']}" for i, t in enumerate(K["themes"], 1))
    await inter.response.send_message(f"## 🟢 The 16 themes\n{lines}\n\nStart one with `/theme`.")


@tree.command(name="annotate", description="Build an annotation from your answers to 4 questions")
async def annotate_cmd(inter: discord.Interaction):
    await start_in_channel(inter, "annotate", "## ✍️ Let's write an annotation\nI'll ask 4 questions. One sentence each is plenty. "
                           "Have the piece in front of you.\n\n" + ANNOTATE_Q[0][1])


@tree.command(name="study", description="Write an artist page step by step (CFPM)")
@app_commands.describe(artist="Which artist? (optional)")
async def study_cmd(inter: discord.Interaction, artist: str = ""):
    if artist:
        a = find(artist, ARTISTS)
        new_session("study", inter.user.id, inter.channel_id, artist=a["name"] if a else artist)
        msg = f"## 🔵 Artist study: {a['name'] if a else artist}\nPick **one** of their works and have it open.\n\n{STUDY_Q[0]}"
        await inter.response.send_message(msg + "\n\n*Type your answer as a normal message. `skip` to skip, `stop` to finish early.*",
                                          embed=artist_embed(a) if a else discord.utils.MISSING)
    else:
        s = new_session("study", inter.user.id, inter.channel_id)
        s["step"] = -1
        await inter.response.send_message("## 🔵 Artist study\nWhich artist are you writing about? Type their name.\n\n*`stop` to finish early.*")


async def artist_ac(inter, current):
    return [app_commands.Choice(name=a["name"], value=a["name"])
            for a in K["artists"] if current.lower() in a["name"].lower()][:25]

study_cmd.autocomplete("artist")(artist_ac)


@tree.command(name="artist", description="See an artist's card from the A to Z")
@app_commands.describe(name="Artist name")
async def artist_cmd(inter: discord.Interaction, name: str):
    a = find(name, ARTISTS)
    if not a:
        return await inter.response.send_message(f"**{name}** isn't in my A to Z yet. Try searching them on Tate or The Art Story (🟣 Part 5 has the links).")
    await inter.response.send_message(embed=artist_embed(a))

artist_cmd.autocomplete("name")(artist_ac)


@tree.command(name="artists", description="List artists for a theme or a pathway")
@app_commands.describe(theme="Filter by theme", pathway="Filter by pathway")
@app_commands.choices(pathway=[app_commands.Choice(name=p, value=p) for p in PATHWAYS])
async def artists_cmd(inter: discord.Interaction, theme: str = "", pathway: app_commands.Choice[str] = None):
    pool = K["artists"]
    title = "All artists"
    if theme:
        t = find(theme, THEMES)
        if t:
            pool = [a for a in pool if t["name"] in a["themes"]]; title = t["name"]
    if pathway:
        pool = [a for a in pool if pathway.value in a["pathways"]]
        title = f"{title} · {pathway.value}" if theme else pathway.value
    if not pool:
        return await inter.response.send_message("No matches. Try a different mix.")
    lines = "\n".join(f"• **{a['name']}**: {a['known_for']}" for a in pool[:25])
    more = f"\n…and {len(pool) - 25} more in the 🟠 A to Z PDF." if len(pool) > 25 else ""
    await inter.response.send_message(f"## 🟠 {title}\n{lines}{more}\n\nPick **two** that grab you, then `/artist` or `/study`."[:1990])

artists_cmd.autocomplete("theme")(theme_ac)


@tree.command(name="word", description="What does an art word mean? Or see a list of describing words")
@app_commands.describe(term="An art word, like 'tone' or 'impasto', or a category like 'texture' or 'mood'")
async def word_cmd(inter: discord.Interaction, term: str):
    t = term.lower().strip()
    out = []
    if t in WORDS:
        d, ex = WORDS[t]
        out.append(f"**{term.title()}**: {d}" + (f"\n*Use it like this: {ex}*" if ex else ""))
    cat = next((k for k in K["describing_words"] if k.lower() == t), None)
    if cat:
        out.append(f"**Describing words for {cat}:** {', '.join(K['describing_words'][cat])}")
    tech = next((k for k in K["technique_words"] if t in k.lower()), None)
    if tech:
        out.append(f"**{tech} words:** {K['technique_words'][tech]}")
    if not out:
        close = [w for w in WORDS if t[:4] in w][:5]
        out.append(f"I don't have **{term}** yet." + (f" Did you mean: {', '.join(close)}?" if close else "") +
                   "\nTry Tate Art Terms (🟣 Part 5) or the 🟡 Art Words PDF.")
    await inter.response.send_message("\n\n".join(out))


async def word_ac(inter, current):
    opts = sorted(set(list(WORDS) + [k.lower() for k in K["describing_words"]]))
    return [app_commands.Choice(name=w, value=w) for w in opts if current.lower() in w][:25]

word_cmd.autocomplete("term")(word_ac)


@tree.command(name="spark", description="A creative push to take your idea somewhere new")
@app_commands.describe(theme="Your theme (optional)")
async def spark_cmd(inter: discord.Interaction, theme: str = ""):
    t = find(theme, THEMES) if theme else None
    w = f"\n🧩 **Word to play with:** *{random.choice(t['words'])}*" if t else ""
    await inter.response.send_message(
        f"## ✨ Spark\nTake whatever you're working on right now…\n\n💭 {random.choice(C.SPARK_WHAT_IF)}\n"
        f"⏱️ **Rule:** {random.choice(C.SPARK_LIMITS)}\n🖍️ **Try it with:** {random.choice(C.SPARK_MATERIALS)}{w}\n\n"
        "It doesn't have to work. Make it, then write **one line** about what happened. Run `/spark` again for a different one.")

spark_cmd.autocomplete("theme")(theme_ac)


@tree.command(name="challenge", description="A quick sketchbook warm-up")
async def challenge_cmd(inter: discord.Interaction):
    n, d = random.choice(C.CHALLENGES)
    await inter.response.send_message(f"## 🎯 {n}\n{d}\n\nPost a photo when you're done. I'd love to see it.")


class StuckView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        for key, (label, _) in C.STUCK.items():
            b = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            b.callback = self.make(key)
            self.add_item(b)

    def make(self, key):
        async def cb(inter: discord.Interaction):
            await inter.response.send_message(f"**{C.STUCK[key][0]}**\n\n{C.STUCK[key][1]}")
        return cb


@tree.command(name="stuck", description="Stuck? Tell me what's going on")
async def stuck_cmd(inter: discord.Interaction):
    await inter.response.send_message("What's going on? Tap the one that fits best.", view=StuckView())


class CheckinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        for n, emo in zip(range(1, 6), ["😣", "😕", "😐", "🙂", "😄"]):
            b = discord.ui.Button(emoji=emo, style=discord.ButtonStyle.secondary)
            b.callback = self.make(n)
            self.add_item(b)

    def make(self, n):
        async def cb(inter: discord.Interaction):
            await inter.response.send_message(C.CHECKIN[n])
        return cb


@tree.command(name="checkin", description="How are you doing today?")
async def checkin_cmd(inter: discord.Interaction):
    await inter.response.send_message("How are you feeling about everything today? 🤍", view=CheckinView())


@tree.command(name="hype", description="A little boost")
async def hype_cmd(inter: discord.Interaction):
    await inter.response.send_message(random.choice(C.HYPE))


@tree.command(name="plan", description="Split your work into small daily chunks")
async def plan_cmd(inter: discord.Interaction):
    await start_in_channel(inter, "plan", "## 📋 Let's make a plan\nType **everything** you need to do, one per line or separated by commas. "
                           "Big or small, just get it out of your head.\n*(Making a new plan replaces your old one.)*")


@tree.command(name="todo", description="See your plan")
async def todo_cmd(inter: discord.Interaction):
    await inter.response.send_message(plan_text(inter.user.id)[:1990])


@tree.command(name="done", description="Tick off a task from your plan")
@app_commands.describe(number="The task number from /todo")
async def done_cmd(inter: discord.Interaction, number: int):
    p = DATA["plans"].get(str(inter.user.id))
    if not p or not (1 <= number <= len(p["tasks"])):
        return await inter.response.send_message("I can't find that task number. Check `/todo`.")
    p["tasks"][number - 1]["done"] = True
    save_data()
    left = sum(not t["done"] for t in p["tasks"])
    msg = f"✅ **{p['tasks'][number - 1]['text']}**: done! " + (random.choice(C.HYPE) if left else "")
    if not left:
        msg += "\n\n🎉 **EVERYTHING IS DONE.** That's huge. Seriously proud of you. Go do something nice for yourself."
    else:
        msg += f"\n{left} to go."
    await inter.response.send_message(msg)


@tree.command(name="ask", description="Ask any question about your course, art, or a topic")
@app_commands.describe(question="Your question")
async def ask_cmd(inter: discord.Interaction, question: str):
    if is_crisis(question):
        return await inter.response.send_message(C.CRISIS_REPLY)
    if ai_allowed(inter.user.id):
        await inter.response.defer(thinking=True)
        DATA["ai_usage"]["count"] = DATA["ai_usage"].get("count", 0) + 1
        save_data()
        try:
            r = await AI.messages.create(model=AI_MODEL, max_tokens=600, system=ai_system(inter.user.id, ASK_NOTE),
                                         messages=[{"role": "user", "content": question}])
            out = "".join(b.text for b in r.content if b.type == "text").strip()
        except Exception as e:
            print("AI ask error:", e)
            out = "My AI brain is having a moment. 😅 Try again in a minute."
        parts = chunks(f"**❓ {question}**\n\n{out}")
        for p in parts:
            await inter.followup.send(p)
        return
    ql = question.lower()
    if any(k in ql for k in ("deadline", "due date", "when is", "when do", "hand in", "hand-in", "unit ", "my tutor", "my teacher")):
        return await inter.response.send_message(
            f"**❓ {question}**\n\nThat one's specific to your college, so **your tutor** is the best person to ask. "
            "It's a quick, normal question for them, honestly. 🙂 Once you know, `/plan` can help you work back from the date."[:1990])
    ans = keyword_reply(question)
    if ans.startswith("I'm a simple bot"):
        ans = ("I can't answer that one on my own yet. 🙈 Here's where to look:\n"
               "• Art words → `/word` or the 🟡 Art Words PDF\n• How you're marked → 🩷 How to Annotate\n"
               "• Artists → `/artist` or the 🟠 A to Z\n• Anything about your course or deadlines → **your tutor**. "
               "It's literally their job, and asking shows independence.")
    await inter.response.send_message(f"**❓ {question}**\n\n{ans}"[:1990])


@tree.command(name="describe", description="Get words to describe your work: send a photo, or tell me what's in it")
@app_commands.describe(photo="A photo of your work (optional)", notes="Anything you want to tell me about it (optional)")
async def describe_cmd(inter: discord.Interaction, photo: discord.Attachment = None, notes: str = ""):
    if ai_allowed(inter.user.id):
        if photo or notes:
            await inter.response.send_message("🔍 Having a good look…")
            return await run_describe(inter.channel, inter.user.id, photo, notes)
        new_session("describe", inter.user.id, inter.channel_id)
        return await inter.response.send_message(
            "## 🔍 Describe your work\nSend me a **photo** of the page (a screenshot works best), or **describe it** in a sentence or two.\n"
            "I'll mark what I notice and give you **words**, never sentences. The writing stays yours. ✍️\n\n*`stop` to cancel.*")
    await inter.response.send_message(
        "## 🔍 Describe your work\nLook at your piece. What can you see in it? Pick everything that applies and I'll give you words for each.",
        view=DescribeView())


@tree.command(name="brief", description="Save your current project brief so I can keep it in mind")
@app_commands.describe(text="Your brief or theme. Leave empty to see it, or type 'clear' to remove it")
async def brief_cmd(inter: discord.Interaction, text: str = ""):
    uid = str(inter.user.id)
    if text.lower().strip() == "clear":
        DATA["briefs"].pop(uid, None); save_data()
        return await inter.response.send_message("Brief cleared. 🧹")
    if text:
        DATA["briefs"][uid] = text[:500]; save_data()
        t = find(text, THEMES) or (THEMES[BRIEF_MAP[text.lower().strip()].lower()] if text.lower().strip() in BRIEF_MAP else None)
        hint = f"\nThis links to **{t['name']}**. Try `/theme {t['name']}` to explore it." if t else ""
        return await inter.response.send_message(f"📌 Saved your brief: *{text[:500]}*{hint}")
    b = DATA["briefs"].get(uid)
    await inter.response.send_message(f"📌 Your brief: *{b}*" if b else "No brief saved yet. Use `/brief` and type it in.")


@tree.command(name="log", description="Log what you did today, however small, and build your streak")
@app_commands.describe(what="What did you do? e.g. 'tone strip in charcoal' or '2 artist pages'")
async def log_cmd(inter: discord.Interaction, what: str):
    uid = str(inter.user.id)
    DATA["logs"].setdefault(uid, []).append({"date": today_local().isoformat(), "text": what[:300]})
    save_data()
    r = mark_yes(inter.user.id)
    pts = f" **+{r[0]} ⭐**" if r else ""
    await inter.response.send_message(f"{random.choice(C.LOG_REPLIES)} *{what[:300]}*{pts}\n{score_line(inter.user.id)}")


@tree.command(name="progress", description="See everything you've done so far")
async def progress_cmd(inter: discord.Interaction):
    uid = str(inter.user.id)
    logs = DATA["logs"].get(uid, [])
    p = DATA["plans"].get(uid)
    lines = ["## 🌱 Your progress"]
    if DATA["briefs"].get(uid):
        lines.append(f"📌 **Brief:** {DATA['briefs'][uid]}")
    lines.append(score_line(inter.user.id) + f" · 📒 **Logged:** {len(logs)}")
    if p and p.get("tasks"):
        done = sum(t["done"] for t in p["tasks"])
        bar = "🟩" * round(10 * done / len(p["tasks"])) + "⬜" * (10 - round(10 * done / len(p["tasks"])))
        lines.append(f"📋 **Plan:** {bar} {done}/{len(p['tasks'])}")
    if logs:
        lines.append("\n**Recently:**")
        for e in logs[-6:][::-1]:
            lines.append(f"• {e['date']}: {e['text']}")
    else:
        lines.append("\nNothing logged yet. Use `/log` after you do anything, even 10 minutes counts.")
    if logs or (p and p.get("tasks")):
        lines.append("\nLook how far you've come. 🤍")
    await inter.response.send_message("\n".join(lines)[:1990])


@tree.command(name="reminders", description="Turn morning plan reminders on or off")
@app_commands.choices(setting=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")])
async def reminders_cmd(inter: discord.Interaction, setting: app_commands.Choice[str]):
    off = DATA["reminders_off"]
    if setting.value == "off" and inter.user.id not in off:
        off.append(inter.user.id)
    if setting.value == "on" and inter.user.id in off:
        off.remove(inter.user.id)
    save_data()
    await inter.response.send_message(f"Morning reminders are **{setting.value}**. 🙂")


@tree.command(name="ping", description="Get a daily sketchbook ping in this channel, tagged with your name")
@app_commands.describe(time="Time for the ping, e.g. 18:00 or 6pm", message="Your own ping message (optional)", off="Turn the ping off")
async def ping_cmd(inter: discord.Interaction, time: str = "18:00", message: str = "", off: bool = False):
    uid = str(inter.user.id)
    if off:
        DATA["pings"].pop(uid, None); save_data()
        return await inter.response.send_message("Daily ping is off. The sketchbook will miss you. 🥲 (`/ping` to turn it back on)")
    m = re.match(r"^\s*(\d{1,2})(?::|\.)?(\d{2})?\s*(am|pm)?\s*$", time.lower())
    if not m:
        return await inter.response.send_message("I didn't understand that time. Try `18:00` or `6pm`.")
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "pm" and h < 12: h += 12
    if ap == "am" and h == 12: h = 0
    if not (0 <= h < 24 and 0 <= mi < 60):
        return await inter.response.send_message("That time doesn't exist. 😅 Try `18:00` or `6pm`.")
    old_p = DATA["pings"].get(uid, {})
    DATA["pings"][uid] = {"channel": inter.channel_id, "time": f"{h:02d}:{mi:02d}", "message": message[:300] or old_p.get("message", ""),
                          "since": old_p.get("since") or today_local().isoformat(), "last": old_p.get("last")}
    player(uid)
    save_data()
    msg = DATA["pings"][uid]["message"] or C.DEFAULT_PING
    await inter.response.send_message(
        f"⏰ Done! Every day at **{h:02d}:{mi:02d}** ({TIMEZONE.split('/')[-1].replace('_', ' ')} time) I'll ping you here with:\n> {msg}\n\n"
        f"**The game:** ✅ Yes = **+{C.POINTS_YES}** · ❌ Not today = **{C.POINTS_NO}** · 👻 No answer = **{C.POINTS_MISS}**\n"
        f"🔁 Missed a day? Do a double session within {C.CATCHUP_DAYS} days and catch up to win it back (**+{C.POINTS_CATCHUP}** bonus).\n"
        f"🔥 Every 7 days in a row = **+{C.STREAK_BONUS}** bonus. Level up from 📄 Blank Page to 👑 Master of the Page.\n"
        f"`/score` to see your stats · `/leaderboard` to see who's winning.")


@tree.command(name="sketched", description="Tell me if you did sketchbook today (same as the ping buttons)")
@app_commands.choices(answer=[app_commands.Choice(name="✅ yes", value="yes"), app_commands.Choice(name="❌ not today", value="no"),
                              app_commands.Choice(name="🔁 catch up (I did extra)", value="catch")])
async def sketched_cmd(inter: discord.Interaction, answer: app_commands.Choice[str]):
    await inter.response.send_message(quest_answer(inter.user.id, answer.value))


@tree.command(name="score", description="Your sketchbook streak, points and level")
async def score_cmd(inter: discord.Interaction):
    uid = inter.user.id
    settle(uid)
    g = player(uid)
    title, nxt = level(g["points"])
    t = today_local()
    week = ""
    for i in range(6, -1, -1):
        d = (t - dt.timedelta(days=i)).isoformat()
        v = g["days"].get(d) or ("yes" if d in done_dates(uid) else None)
        week += {"yes": "🟩", "caught": "🟦", "no": "🟥", "miss": "⬛"}.get(v, "⬜")
    bar = ""
    if nxt:
        lo = max(level_floor(g["points"]), 0)
        frac = max(0, min(1, (g["points"] - lo) / max(1, nxt[0] - lo)))
        bar = "\n" + "▰" * round(frac * 10) + "▱" * (10 - round(frac * 10)) + f" {nxt[0] - g['points']} pts to {nxt[1]}"
    catch = catchable(uid)
    lines = [f"## {title}", f"⭐ **{g['points']} points**{bar}",
             f"🔥 Streak: **{streak(uid)}** · 🏅 Best: **{max(g.get('best', 0), streak(uid))}**",
             f"Last 7 days: {week}", "*🟩 did it · 🟦 caught up · 🟥 not today · ⬛ missed · ⬜ nothing yet*"]
    if catch:
        lines.append(f"\n🔁 You can still win back **{len(catch)}** day(s): do a double session, then `/sketched catch up`.")
    p = DATA["pings"].get(str(uid))
    lines.append(f"⏰ Daily ping: **{p['time']}**" if p else "⏰ No daily ping yet: `/ping` to start the game properly.")
    await inter.response.send_message("\n".join(lines))


def level_floor(points):
    lo = 0
    for need, _ in C.LEVELS:
        if points >= need:
            lo = need
    return lo


@tree.command(name="leaderboard", description="Who's winning the sketchbook game?")
async def leaderboard_cmd(inter: discord.Interaction):
    rows = sorted(((int(u), g["points"]) for u, g in DATA["game"].items() if g.get("days")), key=lambda x: -x[1])[:10]
    if not rows:
        return await inter.response.send_message("Nobody's playing yet! `/ping` to join the game. 🎮")
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    out = ["## 🏆 Sketchbook leaderboard"] + [f"{medals[i]} <@{u}>: **{p} pts** · 🔥 {streak(u)}" for i, (u, p) in enumerate(rows)]
    await inter.response.send_message("\n".join(out), allowed_mentions=discord.AllowedMentions.none())


@tree.command(name="reset", description="Stop any guided chat and start fresh")
async def reset_cmd(inter: discord.Interaction):
    end_session(inter.channel_id, inter.user.id)
    HISTORY.pop(inter.channel_id, None)
    await inter.response.send_message("All reset. 🙂 What do you want to do? (`/help`)")


# ------------------------------------------------------------------ daily prompt (optional)
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(TIMEZONE)
except Exception:
    _TZ = dt.timezone.utc


@tasks.loop(time=dt.time(hour=DAILY_HOUR, tzinfo=_TZ))
async def daily_post():
    ch = bot.get_channel(DAILY_CHANNEL_ID) if DAILY_CHANNEL_ID else None
    if ch:
        n, d = random.choice(C.CHALLENGES)
        await ch.send(f"☀️ **Daily sketchbook warm-up: {n}**\n{d}\n\n{random.choice(C.HYPE)}")
    for uid in list(DATA["plans"]):
        if int(uid) in DATA["reminders_off"]:
            continue
        todo = today_tasks(uid)
        if not todo:
            continue
        try:
            user = await bot.fetch_user(int(uid))
            items = "\n".join(f"⬜ `{i}` {t['text']}" for i, t in todo[:8])
            await user.send(f"☀️ **Morning!** Here's what's on today:\n{items}\n\nJust start with the first one. "
                            f"`/done number` when it's finished. {random.choice(C.HYPE)}\n*(`/reminders off` to stop these)*")
        except Exception as e:
            print("reminder DM failed:", e)


@daily_post.before_loop
async def _wait_ready():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def ping_loop():
    now = dt.datetime.now(LOCAL_TZ)
    today = now.date().isoformat()
    for uid, p in list(DATA["pings"].items()):
        if p.get("last") == today:
            continue
        h, m = map(int, p["time"].split(":"))
        due = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if due <= now <= due + dt.timedelta(hours=2):      # 2-hour grace in case the bot restarted
            p["last"] = today
            save_data()
            try:
                await send_ping(uid, p)
            except Exception as e:
                print("ping failed:", e)


@ping_loop.before_loop
async def _wait_ready2():
    await bot.wait_until_ready()


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("No DISCORD_TOKEN found. On Railway: add it in the Variables tab. On a computer: put it in settings.env. See README.md.")
    bot.run(TOKEN)
