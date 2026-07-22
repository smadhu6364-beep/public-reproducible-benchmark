# Method B rater recruitment — outreach materials

**What this is and isn't.** This drafts the actual outreach message and
qualifying criteria so recruitment is a send-it action, not a from-scratch
writing task. It does not recruit anyone — that step needs a real person
(Madhu/Kruthik) sending this to real contacts. Both decisions that used to
be open (volunteer-vs-paid, spreadsheet-vs-form) are resolved as of
2026-07-22 — see below.

---

## Both open decisions are now resolved (2026-07-22, Madhu)

1. **Volunteer or paid? → Volunteer only.** No budget attached. The honest
   time ask is still **4-6 hours per rater** (45 registers x ~5-8 min each) —
   worth being upfront about in the message rather than downplaying it.
   **Consequence worth naming directly:** this takes the paid-platform
   fallback (`rater_recruitment_channels.md` §2/§4 step 3 - Respondent.io /
   User Interviews, ~3-10 days to 3-5 confirmed raters) off the table. The
   remaining reliable routes are the warm network (§1a, days-2 weeks *if*
   contacts exist) and targeted LinkedIn outreach (§1d, 1-3 weeks, 20-50+
   messages for a 5-15% reply rate) - both real, but with more schedule risk
   than the paid fallback carried, this close to the Aug-2026 deadline. If
   fewer than ~3 are confirmed after the first 1-2 weeks, revisit
   volunteer-only rather than let the deadline slip - APM/PMI's chapter
   routes (§1b/1c) take 2-4+ weeks on their own, too slow as a *fallback*
   started late, though fine as a parallel warm ask started now.
2. **Delivery format → Spreadsheet.** Matches `rater_protocol.md` §5's
   default and needs zero new tooling - `src/build_rater_packets.py`
   already produces each rater's assignment sheet in exactly this shape.

The template below has both filled in - it's send-ready as-is, aside from
the genuinely per-recipient fields ([Name], [DATE], [Madhu]).

---

## Who to approach (qualifying criteria)

Not an ML background — the opposite. Look for:

- **Real project management experience**, ideally on complex, multi-year
  programmes (infrastructure, energy, public-sector, international
  development, or similarly structured projects) — close to what the
  corpus itself covers, so a rater's intuition for "what would an
  experienced PM expect to see" is grounded, not generic.
- **Comfortable with risk registers as a working artifact** — someone who
  has actually written, reviewed, or maintained one, not just heard of the
  concept.
- **Available for ~4-6 hours within a defined window** (see the message
  below) — this is the real constraint given the Aug-2026 deadline; someone
  enthusiastic but unavailable for weeks doesn't help the timeline.
- No need for the reverse: familiarity with LLMs, AI, or this specific
  study's design is not required and arguably shouldn't be selected for —
  the whole point of Method B is an independent, domain-expert judgment.

Plausible sources: colleagues or former colleagues with PM/PMO experience,
university programme-management faculty or alumni networks, professional
bodies (e.g., PMI, APM, or sector-specific equivalents for
international-development/infrastructure work), or LinkedIn outreach
targeted at people with a "Project Manager" / "Programme Manager" title at
relevant organizations (World Bank-adjacent development consultancies, UK
infrastructure delivery bodies, etc. — a deliberate echo of the corpus's own
sources, though this is not a strict requirement).

---

## Ready-to-send invitation (only [Name]/[DATE]/[Madhu] left to fill in)

> Subject: Quick favor — reviewing some project risk registers (~4-6 hrs, volunteer)
>
> Hi [Name],
>
> I'm running an academic benchmark study on AI-generated project risk
> registers (comparing them against real, human-authored ones from World
> Bank and UK government projects), and I need a few experienced project
> management professionals to independently review and score some of the
> output. No AI/ML background needed — the opposite, actually: I need your
> PM judgment, not technical knowledge.
>
> **What it involves:** you'd review 45 short packets. Each one has (1) a
> project's planning documentation and (2) one risk register produced for
> it. You'd score each register on three simple 1-5 questions — does it
> cover what you'd expect, is it accurate and specific rather than generic,
> and are the mitigations actually useful — plus an optional one-line note
> on anything that looks wrong or made up. You won't be told what produced
> each register (that's intentional, to keep your judgment independent).
>
> **Time:** roughly 5-8 minutes per packet, so **4-6 hours total** — doable
> in one sitting or spread across a week or two, whatever works for you.
> I'd need this back by **[DATE]** to stay on schedule.
>
> **Format:** you'll get a spreadsheet with everything laid out — no
> special software needed.
>
> This is a volunteer contribution to an academic study — I know that's an
> ask, and I'd make sure you're acknowledged in the paper if you'd like.
>
> Interested? Happy to answer any questions before you commit. If this
> isn't for you but you know someone who'd be a good fit, I'd appreciate an
> introduction.
>
> Thanks,
> [Madhu]

---

## After someone says yes

Nothing further to draft here — `docs/rater_protocol.md` §5 already has the
full task instructions ready to hand over once a rater is confirmed, and
`src/build_rater_packets.py` already produces each rater's assignment sheet
(blinded, seeded, ready to render into packets the moment real generations
exist). The recruitment step above is the only piece that was actually
missing.
