# ef2.0
A bot for ef to use as a study buddy or guidance for his artwork

## Sketchbook Buddy: setup guide

A Discord bot built on the Art Toolkit. It runs as a **normal bot** and doesn't need a Claude subscription.
AI is an optional extra that unlocks photo scanning and full answers to any question.

---

## What it does

### Works free, no AI needed

| Command | What happens |
|---|---|
| `/theme` | Guided chat about a theme. Asks 3 questions with follow-ups, then gives back a **mind map made only of his own answers**, plus words, two artists, research ideas and a test. Type a brief like "Home" and it picks the closest theme. |
| `/describe` | He picks what he can see in his work (shading, lines, colour, texture…) and gets **word lists** for each, plus "look closely" questions. **Words only, never sentences.** |
| `/annotate` | Asks What / How / Why / Next one at a time, then puts **his** answers together. Flags weak words ("nice", "messy"), counts the art words he used and checks for a "because". |
| `/study` | Walks through an artist page step by step: Content, Form, Process, Mood, opinion, link and response. |
| `/ask` | Answers simple questions (art words, artists, marking, themes). Sends course-specific questions, like deadlines, to his tutor. |
| `/spark`, `/challenge` | A creative push (a "what if", a rule and a material) and quick sketchbook warm-ups. |
| `/artist`, `/artists`, `/word` | Artist cards, artist lists by theme or pathway, and what art words mean. |
| `/brief` | Saves his current brief so the bot keeps it in mind. |
| `/plan`, `/todo`, `/done` | Turns his to-do list into small daily chunks, then ticks them off with hype. |
| `/log`, `/progress` | Logs what he did each day, builds a **streak** 🔥, and shows everything he's achieved so far. |
| Morning reminders | Each morning, he gets a DM with that day's tasks from his plan. `/reminders off` stops them. |
| `/checkin`, `/stuck`, `/hype` | Support: mood buttons, "I'm stuck" options with a tiny next step for each, and encouragement. |

### Extra with AI switched on

| Command | What changes |
|---|---|
| `/describe` + photo | It **scans his photo**, draws **numbered circles** on the parts it notices (e.g. ① *intense dark shading*), and gives **words** for each number, plus overall mood and composition words and two "why" questions. Still **words only**: he writes every sentence himself. |
| `/ask` | Answers **any** question about his course, art or a topic, in plain language. |
| Chat | He can @mention or DM the bot to talk things through. It's taught to ask questions and never hand him ideas. |

**Safety:** if he ever writes something serious (like self-harm), the bot replies with care and gives UK support lines: Samaritans 116 123, text SHOUT to 85258, or 999.

---

## The files

| File | What it is |
|---|---|
| `bot.py` | The bot |
| `content.py` | Everything the bot says. **Edit this to change the wording** or add more sparks, challenges and hype lines. |
| `knowledge.json` | The toolkit content (themes, artists, words) |
| `requirements.txt` | What Python needs to install |
| `Procfile` | Tells hosting services how to start the bot |
| `settings_template.env` | Settings for running it on your own computer |
| `README.md` | This guide |

---

## Step 1: Create the bot on Discord (5 minutes)

1. Go to **discord.com/developers/applications** and log in.
2. Click **New Application**, name it (e.g. *Sketchbook Buddy*), then click **Create**.
3. In the left menu, click **Bot**:
   - Click **Reset Token**, then **Copy**, and save it somewhere safe. This is the bot's password. Never share it or upload it anywhere.
   - Scroll down and switch **Message Content Intent** ON. Click **Save Changes**.
   - Optional: give it a profile picture.
4. In the left menu, click **OAuth2**, then **URL Generator**:
   - Under Scopes, tick **bot** and **applications.commands**.
   - Under Bot Permissions, tick **View Channels**, **Send Messages**, **Read Message History**, **Embed Links**, **Attach Files** and **Use Slash Commands**.
   - Copy the URL at the bottom, open it, and add the bot to your shared server.

---

## Step 2: Put it online so it runs 24/7

**Why it needs a host:** a bot is a program that has to keep running all the time. If it isn't running somewhere, it goes offline.
That "somewhere" doesn't have to be your computer. It can be a computer in the cloud that never switches off.

**GitHub on its own can't do this.** GitHub stores the files, a bit like Google Drive for code, but it doesn't run them.
So the plan is: **files on GitHub → a hosting service that runs them**. Whenever you change a file on GitHub, the host updates the bot automatically.

### Recommended: GitHub + Railway (about 15 minutes, no coding)

**A. Put the files on GitHub**
1. Make a free account at **github.com**.
2. Click **+** (top right), then **New repository**. Name it `sketchbook-buddy`, choose **Private**, then click **Create repository**.
3. Click **uploading an existing file**, drag in all the files **except any `settings.env`** (your token never goes on GitHub), then click **Commit changes**.

**B. Run them on Railway**
1. Go to **railway.com** and sign in with your GitHub account.
2. Click **New Project**, then **Deploy from GitHub repo**, and pick `sketchbook-buddy`.
3. Open the service, go to the **Variables** tab, and add:
   - `DISCORD_TOKEN` = your bot token
   - Optional: `DAILY_HOUR` = `9` and `TIMEZONE` = `Europe/London`
   - Optional: `DAILY_CHANNEL_ID`, `ANTHROPIC_API_KEY` (see the AI section below)
4. **So plans and streaks are never lost:** right-click the service, choose **Attach Volume**, set the mount path to `/data`, then add a variable `DATA_DIR` = `/data`.
5. If Railway asks for a start command, enter `python bot.py`.
6. Open **Deployments**, then **View Logs**. When you see **"Sketchbook Buddy is online"**, it's live. 🎉

**Cost:** Railway gives new accounts a one-time **$5 trial credit**. After that it's the **Hobby plan at $5/month** (around £4 or ₹450), which includes $5 of usage, enough for a small bot like this one.
Pricing can change, so check railway.com.

**To update the bot later:** edit a file on GitHub (for example, add hype lines to `content.py`) and Railway redeploys it automatically.

### Other options

- **A friend who already hosts a bot:** they can run this one alongside it. Send them the files and this guide.
- **Oracle Cloud "Always Free":** free forever, but setup is technical (a Linux server) and it needs a card for sign-up. Good if a techy friend sets it up.
- **An old laptop or a Raspberry Pi at home** that stays on all the time.
- **Not suitable:** Render and Replit free tiers (they go to sleep), GitHub Pages (websites only).

### Running it on your own computer (for testing)
Install **Python 3.10+** from python.org. Put the files in one folder, rename `settings_template.env` to `settings.env`, and paste your token after `DISCORD_TOKEN=`. Then run:
```
pip install -r requirements.txt
python bot.py
```
It only stays online while your computer is on and the window is open.

---

## Step 3: Try it

Type `/help` in your server. Slash commands can take a few minutes to appear the first time. If they don't show up, fully restart Discord.
Good first test: `/brief`, then `/theme`, then `/describe`.

---

## Optional: AI mode (photo scanning and full answers)

- This does **not** use a Claude Pro subscription. It needs a separate API key from **console.anthropic.com**, paid with prepaid credits (top up $5 and it lasts a long time).
- Add it as `ANTHROPIC_API_KEY` (in Railway Variables, or in `settings.env`).
- **Rough cost** on the default `claude-haiku-5-5`: well under 1p per message, including photo scans. `claude-sonnet-5-5` is smarter and costs about 1p per message (set `AI_MODEL`).
- `AI_DAILY_LIMIT` (default 60) caps messages per day. `AI_ALLOWED_USER_IDS` limits who can use AI, so nobody else can run up a bill.
- If the credits run out or the key is removed, the bot automatically goes back to the free version. Nothing breaks.
- The circles on photos are the AI's best guess at where things are. They'll usually be in the right area, but not pixel-perfect.

---

## Optional: daily warm-up in a channel
Turn on Developer Mode in Discord (Settings > Advanced), right-click the channel, then click **Copy Channel ID**. Add it as `DAILY_CHANNEL_ID`. It posts at `DAILY_HOUR`, the same time as the morning reminders.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "No DISCORD_TOKEN found" | Railway: check the variable name is exactly `DISCORD_TOKEN`. Computer: the file must be named exactly `settings.env`. |
| Bot is online but ignores messages | Switch **Message Content Intent** on (Step 1.3), then restart or redeploy the bot. |
| No slash commands showing | Wait a few minutes and restart Discord. Check the bot was invited with **applications.commands** ticked. |
| Morning reminders not arriving | He needs to allow DMs from server members (Server > Privacy Settings), and he needs a plan made with `/plan`. |
| Plans or streaks disappeared after an update | Add the Railway Volume and the `DATA_DIR` variable (Step 2B.4). |
| Bot seems confused | Type `/reset`. |
