"""Everything the bot says that isn't pulled from the toolkit.
Edit freely: change wording, add more lines. Lists are picked from at random."""

# ---------- /spark : prompts to push his OWN idea somewhere new (never an idea itself)
SPARK_WHAT_IF = [
    "What if you made it **huge**, or **tiny**?",
    "What if you only showed **part** of it?",
    "What if you made it out of a material it would **never** normally be made from?",
    "What if it was **falling apart**, or only half finished?",
    "What if you **repeated** it again and again?",
    "What if the **shadow** or the **space around it** was the main subject?",
    "What if you **hid** it, wrapped it, or covered it?",
    "What if you showed it **changing over time**?",
    "What if you showed what it **feels** like rather than what it looks like?",
    "What if you cut it up and **rearranged** it?",
    "What if you looked at it from somewhere **unexpected**: underneath, inside, really far away?",
    "What if it had to work as a **wearable**, a **poster** or a **3D object** instead?",
    "What if you combined it with the **opposite** of itself?",
    "What if you used only **one colour**?",
]
SPARK_LIMITS = [
    "Use your **non-dominant hand**.", "Give yourself **only 5 minutes**.", "Don't lift your pen from the page.",
    "Only use **three marks** of your choice.", "Work **without looking at the paper**.", "Use **only black and white**.",
    "Work **really big**: A2 or bigger.", "Work **really small**: no bigger than a stamp.",
    "Tear instead of cutting.", "Use something that **isn't** an art material.",
]
SPARK_MATERIALS = ["charcoal", "ink and a stick", "collage from old magazines", "masking tape", "wire",
                   "tissue paper and PVA", "a biro", "coffee or tea stain", "thread or stitch", "photos on your phone",
                   "card and scissors", "oil pastel", "a monoprint", "clay or plasticine", "tracing paper layers"]

# ---------- /challenge : quick sketchbook warm-ups
CHALLENGES = [
    ("Blind contour", "Draw an object without looking at the paper at all. 2 minutes. Then do it again. Wobbly is the point."),
    ("Continuous line", "Draw something in your room without lifting your pen once. 5 minutes."),
    ("One object, five ways", "Draw the same object 5 times: pencil, pen, charcoal, collage, and one material of your choice."),
    ("Negative space", "Draw only the spaces around and between things, never the things themselves."),
    ("Tone strip", "Make a strip of 8 boxes going from white to black with one material. Then try a different material."),
    ("Texture hunt", "Take 10 rubbings or close-up photos of different textures around you. Label each with a describing word."),
    ("Zoom in", "Pick something small. Draw a 2cm section of it so it fills a whole page."),
    ("Mark-making page", "Fill a page with 20 different marks using 4 tools. Give each one a describing word."),
    ("Colour from life", "Pick one object and mix 5 colours you can actually see on it. Paint swatches and label them."),
    ("30-second figures", "Sketch people around you (or from a video) in 30 seconds each. Do 10."),
    ("Shadow drawing", "Shine a light on an object and draw only its shadow."),
    ("Wrong hand portrait", "Draw a self-portrait with your non-dominant hand. 5 minutes."),
    ("Photo walk", "Take 15 photos on one walk, all about one theme. Print or sketch your favourite three."),
    ("Layer it", "Draw something, then draw it again on tracing paper over the top, slightly moved."),
    ("Cut and rearrange", "Take an old drawing you don't like. Cut it into strips and rearrange it into something new."),
]

# ---------- generic follow-ups during a /theme chat (reflect, never answer)
FOLLOW_UPS = [
    "Ooh, interesting. **Why** that, do you think?",
    "Nice. If you had to **draw** that, what would you start with?",
    "What **material** do you think would show that best?",
    "Can you think of something **you've seen or photographed** that links to that?",
    "That's a good thread. What **feeling** goes with it?",
    "Love that. Is that something you could go and **collect or photograph** this week?",
    "Good. What would the **opposite** of that look like?",
    "That's a strong starting point. What's the **smallest detail** of it you'd zoom in on?",
]
SHORT_ANSWER_NUDGES = [
    "Could you say a little more? Even one more sentence helps.",
    "Tell me a bit more. What made you think of that?",
]

# ---------- /stuck menu
STUCK = {
    "idea": ("I don't know what to make",
             "Totally normal, and it usually means you need **more research, not more thinking**.\n\n"
             "**Try this:** go back to your theme and collect 10 things for it, like photos, quick sketches or objects. "
             "Don't judge them, just collect. Then ask yourself which one you keep looking at. That's your starting point.\n\n"
             "Want help? Try `/theme` for a guided chat or `/spark` for a push."),
    "write": ("I don't know what to write",
              "Annotation is just answering four questions: **What is it? How did I make it? Why? What next?**\n\n"
              "Try `/annotate` and I'll ask you them one at a time, then put your answers together for you."),
    "much": ("There's too much to do",
             "Let's shrink it. You don't need to do everything today, just the **next tiny step**.\n\n"
             "**Try this:** write down everything on your mind, then pick the one thing that takes under 20 minutes. Do only that.\n\n"
             "Try `/plan` and I'll split your list into days for you."),
    "compare": ("Everyone else is ahead",
                "Other people's sketchbooks always look more finished from the outside. You're seeing their best pages, not their messy ones.\n\n"
                "Foundation is marked on **your own progress and thinking**, not on keeping up with anyone. "
                "Two honest pages with good notes beat ten pretty ones with nothing written."),
    "motivation": ("I can't get started",
                   "Starting is the hardest bit, so make it tiny.\n\n"
                   "**Try this:** set a 10-minute timer and do a `/challenge`. That's it. If you want to stop after 10 minutes, you can. "
                   "Usually you won't want to."),
    "hate": ("I hate what I made",
             "That happens to every artist. The good news: a piece you don't like is **really useful** in a sketchbook.\n\n"
             "**Try this:** write two lines next to it: what went wrong, and what you'd try differently. "
             "That's problem solving and reflection, two of the things you're actually marked on."),
}

# ---------- /checkin responses (1 = struggling, 5 = great)
CHECKIN = {
    1: "I'm really glad you told me. Thank you. 🤍\n\nYou don't have to sort everything out right now. Take a breath, get some water, step away for 10 minutes if you need to.\n\n"
       "When you're ready: is there **one person** you could talk to today, like a friend, family or your tutor? Asking for help is a strength, not a weakness.\n\n"
       "If art stuff is the worry, `/stuck` and `/plan` can help make it smaller.",
    2: "Sounds like a heavy day. That's okay, they happen.\n\nLet's keep it really small: what's **one tiny thing** you could do in 15 minutes? Even a `/challenge` counts. "
       "And if something's bothering you, telling your tutor or someone you trust really does help.",
    3: "Okay is a perfectly good place to be. 🙂\n\nWant to keep some momentum? Try a quick `/challenge`, or `/todo` to see what's next on your list.",
    4: "Love that! Good energy is a great time to tackle the thing you've been putting off. What's next on your list? (`/todo`)",
    5: "YES. 🔥 Ride that wave. Make something today, and write down what made today feel good so you can come back to it.",
}

# ---------- /hype
HYPE = [
    "You're doing better than you think. Seriously. 🤍",
    "Every page you add is progress, even the messy ones. Especially the messy ones.",
    "You don't have to be the best in the room. You just have to keep going, and you are.",
    "Your ideas matter because they're **yours**. Nobody else sees things exactly the way you do.",
    "Behind isn't failing. Behind just means there's a next step, and you can take it.",
    "Asking for help took guts. That's the kind of thing that gets people through Foundation.",
    "Small steps still get you there. One page today is a win.",
    "Being confused is part of making art. It means you're actually exploring.",
    "Proud of you for showing up. That's the hardest part done. ✨",
]

# ---------- safety: only clear, serious phrases (kept narrow on purpose)
CRISIS_PHRASES = [
    "kill myself", "killing myself", "suicide", "suicidal", "want to die", "wanna die", "end my life", "end it all",
    "self harm", "self-harm", "selfharm", "hurt myself", "hurting myself", "cut myself", "cutting myself",
    "no reason to live", "better off without me", "don't want to be alive", "dont want to be alive",
]
CRISIS_REPLY = (
    "I'm really glad you said something, and I'm taking it seriously. 🤍\n\n"
    "I'm just a bot, so I can't give you the support you deserve right now, but real people can, any time:\n"
    "• **Samaritans**: call **116 123** (free, 24/7, UK)\n"
    "• **Shout**: text **SHOUT** to **85258** (free, 24/7, UK)\n"
    "• If you're in danger right now, call **999**.\n\n"
    "Please also tell someone you trust today, like a friend, family member or your tutor. You don't have to go through this alone."
)

WELCOME = (
    "Hi! I'm your sketchbook buddy. 🎨 I'm here to help you **think**, not to think for you. "
    "Your ideas are what make your work yours, so I'll mostly ask questions and point you to the right tools.\n\n"
    "Type `/` to see everything I can do, or try `/help`."
)

# ---------- /describe without AI: what he can pick, extra word lists, and "look closely" questions
DESCRIBE_OPTIONS = [
    ("tone", "Shading and tone", "🌗"), ("line", "Lines and marks", "✏️"), ("colour", "Colour", "🎨"),
    ("texture", "Texture", "🧶"), ("form", "Shapes and form", "🔷"), ("composition", "Composition and space", "🖼️"),
    ("mood", "Mood and feeling", "💭"), ("materials", "Materials and technique", "🖌️"),
]
DESCRIBE_EXTRA = {
    "form": ["geometric", "organic", "angular", "rounded", "flat", "three-dimensional", "solid", "hollow", "simplified",
             "distorted", "elongated", "fragmented"],
    "line": ["mark-making", "hatching", "cross-hatching", "stippling", "contour", "outline", "rhythmic", "directional"],
    "tone": ["chiaroscuro", "highlight", "mid-tone", "cast shadow", "tonal range", "blended", "layered"],
}
LOOK_Q = {
    "tone": ["Where is the **darkest** part, and where is the **lightest**?", "Did you build the shading up slowly or put it down in one go?"],
    "line": ["Are your lines mostly **careful** or mostly **quick**?", "Do the lines show an outline, a texture, or movement?"],
    "colour": ["Are your colours **warm**, **cool**, or a mix?", "Which colour does your eye go to first?"],
    "texture": ["If you could touch it, what would it **feel** like?", "Is the texture real (built up) or drawn to look real?"],
    "form": ["Do the shapes look **flat** or **3D**?", "Are the shapes mostly **natural** or **man-made**?"],
    "composition": ["Where does your eye go **first**, and where does it travel next?", "Is the subject in the middle, off to one side, or cropped?"],
    "mood": ["What **one word** sums up how it feels?", "What in the piece (colour, mark, scale) creates that feeling?"],
    "materials": ["What did you use, and what did it do that surprised you?", "Would a different material change the feeling?"],
}

# ---------- /log replies
LOG_REPLIES = [
    "Logged! ✍️", "Nice, that counts. ✅", "Added to your log. Look at you go. 🔥", "Logged. Every page is progress. 🌱",
]

# ---------- Sketchbook Quest (the streak game)
DEFAULT_PING = "🎨 **SKETCHBOOK NOW! OR YOU WILL FOREVER HOLD THIS GUILT!**"
POINTS_YES = 10          # did sketchbook today
POINTS_NO = -5           # honest "not today"
POINTS_MISS = -10        # didn't answer at all (honesty pays!)
POINTS_CATCHUP = 5       # bonus on top of winning back what you lost
STREAK_BONUS = 25        # every 7 days in a row
CATCHUP_DAYS = 2         # how many days back you can still catch up

LEVELS = [  # (points needed, title)
    (-10**9, "💀 In Debt to the Sketchbook"),
    (0, "📄 Blank Page"),
    (50, "✏️ Doodler"),
    (150, "🖍️ Sketcher"),
    (300, "🎨 Artist in Training"),
    (500, "🖌️ Page Filler"),
    (800, "🏆 Sketchbook Legend"),
    (1200, "👑 Master of the Page"),
]
YES_LINES = [
    "YES. The sketchbook is pleased. 🙌", "Another page conquered. 🗡️", "That's how it's done. 🔥",
    "The guilt has been defeated. ✨", "Sketchbook fed. It purrs. 🐈", "Look at you, actually doing it. Proud. 🤍",
]
NO_LINES = [
    "Honest answer, respect. 🫡 But the sketchbook is… disappointed.",
    "Okay. The sketchbook will remember this. 👁️",
    "Noted. Somewhere, a blank page sheds a single tear. 🥲",
    "Fair. Tomorrow we ride again. 🐎",
]
MISS_LINES = [
    "💀 You ghosted the sketchbook yesterday.", "👁️ The sketchbook noticed you didn't show up yesterday.",
    "🕯️ Yesterday's page waited for you. All night.",
]
CATCHUP_LINES = [
    "🔁 Comeback! Lost day reclaimed. The sketchbook forgives you. 😌",
    "🔁 Time recouped. Streak saved. Main character energy. ✨",
]
