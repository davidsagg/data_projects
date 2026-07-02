# #N — BandKit: Building a Stage Companion for Working Bands

### Turning a pile of PDF chord sheets into a live, transposable setlist — and what I learned building it end to end

> **Format note for Substack:** paste this straight into the editor. Wherever you see a `📷 [Image: ...]` marker, drop the matching screenshot or diagram. Set the post number (`#N`) to the next in your *Case Studies* series. Suggested subtitle is the italic line above; suggested tags: `build-to-learn`, `react`, `fastapi`, `music-tech`.

📷 [Image: BandKit musician mode — a chord sheet on a dark stage view, with the transpose controls visible]

#### **Introduction and Context**

Anyone who has played a live show knows the small chaos behind it. The setlist lives in a WhatsApp message, the chord sheets live in a folder of PDFs (or a physical binder), the "who plays what" lives in someone's head, and the moment a singer asks to drop a song *"one tone down"*, everyone scrambles. The tools that exist are either great at **charts** (iReal Pro, Piascore) or great at **organization** (Notion, spreadsheets) — rarely both, and almost never optimized for the one context that matters most: **being on stage, under lights, with no time to fiddle.**

BandKit is my attempt to close that gap: a single, **local-first** web app that handles the whole lifecycle of a show — calendar, song library, setlist, and a stage view where each musician transposes and navigates chords in real time from their own phone.

But there's a second, more honest reason this project exists. BandKit is part of my **"Build To Learn"** portfolio — projects I build end to end specifically to grow as an engineer. Coming off two Python/data-heavy projects (MusicDNA AI and Trend Radar), I deliberately picked a project that would force me into unfamiliar territory: a real React frontend, a dual-mode UX problem, a domain algorithm written from scratch, and offline-first constraints. This article is the story of that build.

> **Build To Learn:** the practice of choosing a project not for the feature it ships, but for the specific skills it forces you to develop. The product is real; the primary output is the learning.

The question I set out to answer was simple to state and hard to execute:

- **Can a single local app serve two completely different users — a calm "organizer" and a high-pressure "performer" — from the same data, and do the hard music-theory work (transposition) instantly and correctly?**

#### **Understanding the Problem**

Before writing code, I framed the project as a proper charter: two modes, one platform.

**Admin mode** is the planning surface — a calendar of shows, rehearsals and recordings; a song library fed by PDF uploads; and a drag-and-drop setlist builder per event, including who plays each song.

**Musician mode** is the stage surface — deliberately stripped down. The next show's setlist in a sidebar; tap a song and the full chord sheet fills the screen in large type on a dark background; `+` / `−` transpose every chord instantly; `←` / `→` jump between sections. The screen never sleeps, and it all works offline.

📷 [Image: Admin mode — calendar and setlist builder side by side]

The methodology mirrored how I run real projects: **7 phases** — charter, user stories, test cases, XP development, TDD, optimization, and deploy — each one documented as I went. That structure is not bureaucracy; it's what let a solo build stay honest about scope and quality.

#### **The Technical Heart — The Chord Pipeline**

The feature that makes or breaks BandKit is the pipeline that turns a **digital PDF chord sheet** into a **structured, transposable score**. It runs in four stages:

📷 [Image: `docs/images/bandkit_chord_pipeline.png` — ready to upload]

1. **Extraction.** `pdfplumber` pulls raw text from the PDF while preserving the line layout — which matters, because a chord sheet's meaning lives in the *vertical alignment* of chords over lyrics.
2. **Parsing.** A custom parser tags each line as a *chord line*, a *lyric line*, or a *section* (`[Intro]`, `[Verse]`, `[Chorus]`) using regex and heuristics, then emits a proprietary **BandKit ChordPro** format (`.bkcp`).
3. **Transposition.** A from-scratch engine shifts every chord by N semitones.
4. **Rendering.** React draws the chords aligned above the correct syllables, in the stage-optimized viewer.

The transposition engine is the piece I'm most proud of, because it's pure domain modeling. It follows standard 12-tone chromatic theory:

> **Transposition:** moving every note (and therefore every chord) of a piece up or down by the same interval, so the song sounds in a new key while keeping its internal relationships intact.

Each chord is split into a **root** and a **suffix** — `C#m7` becomes root `C#` and suffix `m7`. The root is normalized for enharmonic equivalents (`Db → C#`), shifted N positions along the chromatic scale, and the chord is rebuilt. So `transpose("Am", +3)` returns `C#m`, and the lyrics are never touched.

A subtle but important decision: I **mirrored this exact logic in JavaScript** on the frontend. The single most latency-sensitive action in the whole app is a musician hitting `−1` mid-song. Doing that with a network round-trip to the backend would be a felt delay on stage. Mirroring the algorithm made it instant.

#### **What I Explored (and Where It Got Hard)**

**Dual-mode UX turned out to be a data problem, not a UI problem.** My first model tied the stage playback order directly to the planning setlist. It fell apart the moment a band wanted to *plan* a show in one order but *play* it in another. The fix was to model a `MusicalExecution` entity independent of the setlist — a refactor, not a paint job. Lesson: when a UI feels awkward, look at the schema underneath it first.

**Real-world chord sheets are gloriously messy.** PDFs from the wild mix tablature, chord diagrams, and even Spanish key markers (`Tono:`). No parser is going to be perfect against that, so instead of chasing 100% extraction, I built two things: heuristics that get most sheets right, and an always-available manual-edit fallback (edit the `.bkcp` directly) for the rest. Designing for the failure case up front was more valuable than polishing the happy path.

**Offline is an engineering constraint, not a checkbox.** Stages and bars have terrible Wi-Fi. BandKit is a PWA with a Service Worker (Workbox, StaleWhileRevalidate) so it keeps working after first load, and it uses the **WakeLock API** to stop phones from going dark mid-song — a tiny detail that's completely obvious the first time it saves you.

**TDD across two languages.** The backend grew under `pytest` (37 tests, 85% coverage); the critical React pieces — the chord viewer and transpose controls — under `Vitest` and Testing Library (6 tests). Ending at **43 green tests** wasn't about a number; it was about being able to refactor the setlist model (see above) without fear.

📷 [Image: terminal — `make test` output showing 43 passing tests]

The rough edges were rarely the "hard" algorithm and almost always the integration seams: a Vite dev-proxy fighting DevContainer port forwarding, CORS, binding uvicorn to `--host 0.0.0.0`. My git history is an honest log of those small battles — which is exactly the point of Build To Learn.

#### **Result**

The outcome is a working v1: a local app where a band leader plans a show in admin mode, uploads PDFs that get parsed automatically, and every musician opens the setlist on their own device and plays from a transposable, always-on, offline-capable chord viewer. The stack that got there:

- **Backend:** Python 3.11 · FastAPI · SQLAlchemy · Alembic · SQLite · pdfplumber
- **Frontend:** React 18 · TypeScript · Vite · Tailwind · Zustand · vite-plugin-pwa
- **Quality:** 43 tests green, packaged with a Makefile and an optional DevContainer/Docker setup

#### **Conclusion**

BandKit answered its question: yes, one local app *can* serve both the organizer and the performer from shared data, and it can do the music-theory heavy lifting instantly and correctly — as long as you treat the stage as a first-class, hostile-network environment and let the data model, not the UI, carry the dual-mode complexity.

More than the product, the value was the stretch: my first real React + TypeScript frontend, a domain algorithm built and tested from scratch, and offline engineering for a genuine constraint. The next steps I'm eyeing — real-time sync between devices, a teleprompter-style auto-scroll, and OCR for scanned sheets — are each their own small "Build To Learn" in waiting.

See you next time!

*Did you enjoy the content? Subscribe to get updates and new articles!*
