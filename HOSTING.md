# Hosting the Engine for Demonstration

How to get the engine live at a URL you can show someone, what it costs, and
what to do differently once real client data is involved.

## What changed to make this hostable

The engine itself (`core/`, `knowledge/`, `simulate/`) is unchanged — it's
still pure Python with no network dependency. Two things were added on top:

- **`api.py`** — a thin FastAPI wrapper. It serialises `DecisionState` and
  `Action` to and from JSON and calls `Simulation.step()`. It contains zero
  governance logic; it's transport only.
- **`Dockerfile`** — packages the app so any container host can run it.

This has already been tested locally end-to-end: the health check, fetching
a fresh scenario, and stepping through a blocked action all work correctly
over plain HTTP.

## Recommended host: Render

**Use Render, not Railway, for anything client-facing.** Railway has had
five published outage postmortems since November 2025, including an
eight-hour full platform blackout in May 2026 — not what you want mid-pitch.
Render is the more boring, more reliable choice and costs very little more.

**Cost: the $7/month Starter plan** (0.5 CPU, 512MB RAM) is enough for a
demo used by a handful of people at a time. Render's free tier exists but
spins down after 15 minutes of inactivity, with a 30–60 second cold start
on the next request — acceptable for nobody watching you demo something live.
Pay the $7.

## Steps

1. **Put the code in a Git repository** (GitHub is easiest — Render deploys
   directly from it). Push the `governance_engine/` folder as the repo root.

2. **Create a Render account**, then **New → Web Service**, and connect the
   GitHub repo.

3. **Render auto-detects the Dockerfile.** Confirm:
   - Runtime: Docker
   - Instance type: **Starter ($7/month)** — not Free, for the cold-start reason above
   - Region: pick whichever is closest to wherever you'll be demoing from,
     or closest to KCB if latency to their reviewers matters more

4. **Deploy.** Render builds the Docker image and gives you a URL like
   `https://your-service-name.onrender.com`. That URL is now live and public.

5. **Verify it**, exactly as tested above:
   ```bash
   curl https://your-service-name.onrender.com/
   curl https://your-service-name.onrender.com/scenario/board-crisis
   ```

6. **Custom domain (optional, cheap, worth it for a pitch):** Render lets you
   attach a custom domain on the Starter plan at no extra cost beyond the
   domain itself (~$10–15/year from any registrar). `demo.yourplatform.com`
   reads far better in front of KCB than `your-service-name.onrender.com`.

## What you get for the demo

A live URL that serves the click-through front end directly at the root
(`/`) — the "Board Minutes" page, styled as a numbered minute book with
the current facts, who's present, and a set of action buttons matching
the scenario's branch points. This is a genuinely better demo experience
than either the raw JSON endpoints or `demo.py`'s console transcript: a
non-technical person in the room, someone from KCB's MSc programme, can
drive it themselves — declare the interest, send the NEDs out of the
room, watch the vote get blocked, bring them back, watch it succeed,
then watch the filing and capital maintenance consequences play out.

The two JSON endpoints (`/scenario/board-crisis` and
`/scenario/board-crisis/step`) are what the front end calls; they're
still there and still usable directly if you want to script something
else against the engine later.

No separate front-end build step is needed — `static/index.html` is a
single self-contained file (inline CSS and JS, no dependencies), served
by the same FastAPI app via `FileResponse`. Deploying the API deploys
the demo.

## What NOT to do yet

Don't add a database, don't add user accounts, don't add multi-tenancy.
This is a single shared demo instance showing a constructed (parametric)
scenario with no real data in it — exactly the category from the data
sources design that's safe to host centrally with no confidentiality
exposure. Keep it that way until there's an actual reason to add state.

## The one thing to change before this touches any real client data

CORS is currently wide open (`allow_origins=["*"]`) because it's a public
demo. The moment this stops being a demo and starts being a real deployment
— even a Companion-adjacent one — that needs to be locked down to specific
origins, and the stateless design (caller holds the state) needs to become
server-side session storage. Neither is needed for demonstrating to KCB.
Both are needed before anyone's real decision data touches this.
