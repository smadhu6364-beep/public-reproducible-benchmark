# Method B rater recruitment — outreach materials

**What this is and isn't.** This drafts the actual outreach message and
qualifying criteria so recruitment is a send-it action, not a from-scratch
writing task. It does not recruit anyone — that step needs a real person
(Madhu/Kruthik) sending this to real contacts. Two decisions are flagged
below as still open; resolve them before sending, not after.

---

## Two decisions to make before sending (not mine to make)

1. **Volunteer or paid?** `docs/rater_protocol.md` §6 flags this explicitly
   and leaves it open. The honest time ask is **4-6 hours per rater** (45
   registers x ~5-8 min each) — substantial enough that "volunteer" is a real
   ask, not a formality. If there's any budget for even a small honorarium
   or a gift card, it will materially widen who says yes and how fast.
2. **Delivery format:** a spreadsheet (simplest, no new tooling) vs. a
   Google Form (nicer UX, more setup). `rater_protocol.md` §5 recommends the
   spreadsheet by default. Pick one before the first invitation goes out, so
   the message below can say "you'll get a spreadsheet" concretely rather
   than "we'll figure out the format."

Everything below assumes these get resolved first; the template has a
placeholder for both.

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

## Ready-to-send invitation (edit the bracketed parts)

> Subject: Quick favor — reviewing some project risk registers (~4-6 hrs, [PAID/VOLUNTEER])
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
> **Format:** you'll get a [spreadsheet / form link] with everything laid
> out — no special software needed.
>
> [If paid: There's a [$X / gift card] thank-you for your time.]
> [If volunteer: This is a volunteer contribution to an academic study — I
> know that's an ask, and I'd make sure you're acknowledged in the paper if
> you'd like.]
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
