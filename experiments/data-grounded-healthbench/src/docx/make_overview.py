#!/usr/bin/env python3
"""Generate a high-level, plain-language Word overview of the project.

Run from this experiment dir:  .venv/bin/python src/docx/make_overview.py
Output: docs/Data-Grounded-Health-AI-Overview.docx  (repo root, a high-level idea doc)

Plain prose only: all-black text, no tables or dividers, bullet points where
they help. Contains only high-level prose + aggregate numbers (no verbatim
HealthBench prompts/rubrics), so it is safe to share.
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn

# Repo root is four levels up: src/docx/ -> src -> <experiment> -> experiments -> root
OUT = Path(__file__).resolve().parents[4] / "docs" / "Data-Grounded-Health-AI-Overview.docx"
BLACK = RGBColor(0, 0, 0)


def strip_borders(style):
    """Remove the bottom-border line baked into built-in Title/Heading styles."""
    pPr = style._element.find(qn("w:pPr"))
    if pPr is not None:
        for bdr in pPr.findall(qn("w:pBdr")):
            pPr.remove(bdr)


def main():
    doc = Document()
    base = doc.styles["Normal"]
    base.font.name = "Calibri"
    base.font.size = Pt(11)

    # the visible line under the title comes from these styles, not our content
    for name in ("Title", "Heading 1", "Heading 2", "Subtitle"):
        if name in doc.styles:
            strip_borders(doc.styles[name])

    def h(text, level):
        p = doc.add_heading(text, level=level)
        for r in p.runs:
            r.font.color.rgb = BLACK
        return p

    def body(text):
        return doc.add_paragraph(text)

    def bullets(items):
        for it in items:
            doc.add_paragraph(it, style="List Bullet")

    # ---- title ----
    t = doc.add_heading("Evaluating Health AI the Way It's Actually Used", level=0)
    for r in t.runs:
        r.font.color.rgb = BLACK
    sub = doc.add_paragraph("Grounding health-AI benchmarks in the patient's own data")
    sub.runs[0].italic = True
    sub.runs[0].font.size = Pt(12)
    sub.runs[0].font.color.rgb = BLACK

    # ---- core idea ----
    h("The core idea", 1)
    body(
        "Today's leading test for health AI (OpenAI's HealthBench) grades an AI assistant "
        "purely on a typed conversation, as if the only thing the AI knows is what the "
        "patient just said. But real health assistants, the kind that run on a wearable or a "
        "connected-health app, also have the patient's data: their medications, allergies, "
        "lab results, vital signs, and history. We extend the benchmark so the AI is tested "
        "with that data in hand, much closer to how it is really used. Doing so changes both "
        "what the right answer is and how the answer should be scored."
    )

    # ---- problem ----
    h("The problem with today's tests", 1)
    body(
        "The existing scoring guides were written assuming the AI knows nothing about the "
        "patient. So they reward the AI for asking questions like “what medications are "
        "you taking?” That is exactly right when nothing is known, but it is the wrong "
        "behavior when the medication list is already on file. In that case the AI should "
        "simply use the information it has. Because the old scoring guide still expects the "
        "question, it gives the better, data-aware answer a worse score."
    )
    body(
        "This raises a natural question: how often do these test conversations already "
        "include the patient's data at all? The benchmark's own paper does not report this, "
        "so we measured it. We used an AI to read each conversation and decide, separately "
        "for each kind of health data, whether the patient's own data was actually present "
        "rather than just mentioned as a topic. The categories we checked were: medications "
        "the person takes, lab or test results, vital signs, wearable or sensor readings, and "
        "medical records or clinical notes."
    )
    body(
        "We checked this two ways, to be confident in the number. A fast keyword scan over "
        "all 5,000 conversations gave a conservative lower bound, and the more careful AI "
        "reader judged a random sample of 600 conversations, which gives the main estimate "
        "along with a margin of error. The two agreed in direction, and the AI reader caught "
        "real cases the keyword scan missed, such as drug classes (“a blood pressure pill”), "
        "data described in other languages, and values stated in plain words (“blood pressure "
        "dropped to 95”)."
    )
    body(
        "The results were clear. Only about 1 in 6 conversations (about 16.8%, with a 95% "
        "confidence range of roughly 14% to 20%) already include the patient's own structured "
        "data. If we also count conversations that merely state a diagnosis or condition "
        "without any actual values, the figure rises to about 1 in 4 (about 25%). Broken down "
        "by category:"
    )
    bullets([
        "medications the person takes: about 8% of conversations",
        "medical records or clinical notes: about 6%",
        "lab or test results: about 6%",
        "vital signs: about 3%",
        "wearable or sensor data: about 0%, essentially none",
    ])
    body(
        "In other words, roughly 83% of the test conversations are effectively data-blind, and "
        "almost none contain wearable data, even though a real assistant running on a watch or "
        "a health app would have exactly that kind of information. The test is built around a "
        "situation where the AI knows very little about the patient, which is the opposite of "
        "how these systems are actually used."
    )

    # ---- what we found ----
    h("What we found", 1)
    body(
        "We took 30 real HealthBench cases and gave the AI a matching patient record. Under "
        "the original scoring guide, an answer that ignored the data and simply asked "
        "questions scored 59% on average, while an answer that correctly used the patient's "
        "data scored only 42%. In other words, the test rewarded the worse behavior: in 19 "
        "of the 30 cases the original guide actively penalized the AI for using the patient's "
        "data. Once we updated the scoring guide to reflect that the data is now available, "
        "that same data-aware answer scored 71%, as it should."
    )
    body(
        "The deeper point is that the old test mixes up two different things. One is whether "
        "the AI asked the right questions; the other is whether it correctly used what it "
        "already knows. The old test rewards the first while punishing the second. Our "
        "approach separates them, and measures the one that actually matters once the AI is "
        "deployed with real user data."
    )
    body(
        "It is worth being precise about what is and is not broken here. The old scoring "
        "guide is not wrong on its own terms. It was written for a setting where the AI knows "
        "only what the patient typed, and in that setting, asking for the missing history is "
        "the right thing to do. The catch is that this assumption is hidden inside the guide, "
        "and real products break it: an assistant on a watch or a health app already has the "
        "record. So the old guide quietly measures a situation the product is never actually "
        "in. We are not fixing a mistake in the guide. We are measuring the situation that "
        "real use is in."
    )
    body(
        "This also clarifies what good behavior looks like. It is not simply to always use "
        "the data. It is to ask when the data is missing, use it when it is there, and point "
        "out the problem when the data disagrees with itself. A good assistant should adjust "
        "to whatever information it happens to have."
    )

    # ---- contribution ----
    h("Our contribution", 1)
    bullets([
        "Evidence that current health-AI tests systematically mis-score the correct behavior "
        "once the patient's data is present, and sometimes even penalize it. This shows that "
        "static, text-only tests are not enough for how health AI is actually used.",
        "A method to automatically build the better test: take an existing case, generate a "
        "realistic matching patient record, and update the scoring guide to match. It reuses "
        "the doctor-written material rather than starting from scratch.",
        "A shift in what we measure, from asking the right questions to correctly using the "
        "information already on hand, which is the capability that matters in deployment. As a "
        "bonus, this also surfaces real AI mistakes the old test hid, such as an AI that had "
        "the medication on file but still gave a vague, hedged answer.",
    ])

    # ---- why a test ----
    h("Why build a better test, instead of just a better AI?", 1)
    body(
        "It is far easier to create a realistic patient record that fits a conversation than "
        "to build an AI that correctly interprets any patient's messy, real-world data. A "
        "test only has to describe what a good answer looks like, for cases we choose, and it "
        "can take its time. A deployed AI has to produce the good answer instantly, for every "
        "patient. That gap is why we can automate the test even though we cannot automate a "
        "perfect model. And a good test is precisely what model-builders need, because it "
        "turns “use the data well” into a concrete, measurable target to aim at."
    )

    # ---- study directions ----
    h("What we want to study next", 1)
    body(
        "The score drop is only the starting point. It opens a set of sharper questions, each "
        "of which we can study with synthetic data and each of which connects to existing "
        "research:"
    )
    bullets([
        "Is the test fair? We build the patient record from the same question and scoring "
        "guide, so the record is, by design, relevant to the question. That makes for a clean "
        "experiment, but real records are not tidied up for the question being asked. We need "
        "to study how much of the effect depends on how we create the data, and to test the "
        "AI against records that are only partly relevant, or not relevant at all.",
        "Different data situations. Real use is not always clean. Sometimes there is no data, "
        "sometimes the key piece is missing, sometimes the data is noisy or out of date, and "
        "sometimes it is complete and reliable. We want to check that the AI does the right "
        "thing in each case: asking when it should, and using the data when it should, "
        "instead of always doing one or the other.",
        "Finding the signal in a full record. So far we give the AI only the relevant facts. "
        "In reality it would receive a whole medical history, most of which has nothing to do "
        "with the current question. We want to test whether it can pick out what matters "
        "without being misled by the rest.",
        "Wearable sensor data. Watches and health apps produce streams of numbers over time, "
        "such as heart rate and sleep. Reading trends in this kind of data is a different and "
        "harder skill than reading a typed description, and today's text-only tests never "
        "check it. This is a key direction for a platform built around wearables.",
    ])

    # ---- status ----
    h("Where we are, and what's honest about it", 1)
    body(
        "This is an early proof of concept: 30 cases, synthetic (not real) patient data, and "
        "scoring-guide updates generated by AI rather than vetted by clinicians. The numbers "
        "are a demonstration of the effect, not a final measurement. The next steps are to "
        "have physicians validate the updated scoring guides, expand beyond 30 cases, and run "
        "the test across the same set of AI models the original benchmark used."
    )

    doc.save(OUT)
    print(f"wrote {OUT.resolve()}  ({len(doc.paragraphs)} paragraphs)")


if __name__ == "__main__":
    main()
