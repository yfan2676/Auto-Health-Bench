# Evaluating Health AI the Way It's Actually Used

*Grounding health-AI benchmarks in the patient's own data*

## The core idea

Today's leading test for health AI (OpenAI's HealthBench) grades an AI assistant purely on a typed conversation, as if the only thing the AI knows is what the patient just said. But real health assistants, the kind that run on a wearable or a connected-health app, also have the patient's data: their medications, allergies, lab results, vital signs, and history. We extend the benchmark so the AI is tested with that data in hand, much closer to how it is really used. Doing so changes both what the right answer is and how the answer should be scored. Though there are already works that provide EHR environment to agents, and we have to distinguish from them.

## The problem with today's tests

The existing scoring guides were written assuming the AI knows nothing about the patient. So they reward the AI for asking questions like “what medications are you taking?” That is exactly right when nothing is known, but it is the wrong behavior when the medication list is already on file. In that case the AI should simply use the information it has. Because the old scoring guide still expects the question, it gives the better, data-aware answer a worse score.

This raises a natural question: how often do these test conversations already include the patient's data at all? The benchmark's own paper does not report this, so we measured it using an LLM to read each conversation and decide whether the patient's own data was present rather than just mentioned as a topic. The categories we checked were medications the person takes, lab or test results, vital signs, wearable or sensor readings, and medical records or clinical notes.

We checked this two ways, to be confident in the number. A fast keyword scan over all 5,000 conversations gave a conservative lower bound, and the more careful AI reader judged a random sample of 600 conversations, which gives the main estimate along with a margin of error. The two agreed in direction, and the AI reader caught real cases the keyword scan missed, such as drug classes (“a blood pressure pill”), data described in other languages, and values stated in plain words (“blood pressure dropped to 95”).

The results were clear. Only about 1 in 6 conversations (about 16.8%, with a 95% confidence range of roughly 14% to 20%) already include the patient's own structured data. If we also count conversations that merely state a diagnosis or condition without any actual values, the figure rises to about 1 in 4 (about 25%). Broken down by category:

- medications the person takes: about 8% of conversations
- medical records or clinical notes: about 6%
- lab or test results: about 6%
- vital signs: about 3%
- wearable or sensor data: about 0%, essentially none

In other words, roughly 83% of the test conversations are effectively data-blind, and almost none contain wearable data, even though a real assistant running on a watch or a health app would have exactly that kind of information. The test is built around a situation where the AI knows very little about the patient, which is the opposite of how these systems are actually used.

## Preliminary test to “break” the benchmark/rubrics

We took 30 real HealthBench cases and gave the AI a synthetic matching patient record. Under the original scoring guide, an answer that ignored the data and simply asked questions scored 59% on average, while an answer that correctly used the patient's data scored only 42%. In other words, the test rewarded the worse behavior: in 19 of the 30 cases the original guide actively penalized the AI for using the patient's data. Once we updated the scoring guide to reflect that the data is now available, that same data-aware answer scored 71%, as it should.

**The deeper point is that the old test mixes up two different things. One is whether the AI asked the right questions; the other is whether it correctly used what it already knows. The old test rewards the first while punishing the second. Our approach separates them, and measures the one that actually matters once the AI is deployed with real user data.**

It is worth being precise about what is and is not broken here. The old scoring guide is not wrong on its own terms. It was written for a setting where the AI knows only what the patient typed, and in that setting, asking for the missing history is the right thing to do. The catch is that this assumption is hidden inside the guide, and real products break it: an assistant on a watch or a health app already has the record. So the old guide quietly measures a situation the product is never actually in. We are not fixing a mistake in the guide. We are measuring the situation that real use is in.

**This also clarifies what good behavior looks like. It is not simply to always use the data. It is to ask when the data is missing, use it when it is there, and point out the problem when the data disagrees with itself. A good assistant should adjust to whatever information it happens to have.**

## Our proposed contribution

- Evidence that current health-AI tests systematically mis-score the correct behavior once the patient's data is present, and sometimes even penalize it. This shows that static, text-only tests are not enough for how health AI is actually used.
- A method to **automatically** build the better test: take an existing case, generate a realistic matching patient record, and update the scoring guide to match. It reuses the doctor-written material rather than starting from scratch.
- A shift in what we measure, from asking the right questions to correctly using the information already on hand, which is the capability that matters in deployment. As a bonus, this also surfaces real AI mistakes the old test hid, such as an AI that had the medication on file but still gave a vague, hedged answer.

## Why build a better test, instead of just a better AI?

It is far easier to create a realistic patient record that fits a conversation than to build an AI that correctly interprets any patient's messy, real-world data. A test only has to describe what a good answer looks like, for cases we choose, and it can take its time. A deployed AI has to produce the good answer instantly, for every patient. That gap is why we can automate the test even though we cannot automate a perfect model. And a good test is precisely what model-builders need, because it turns “use the data well” into a concrete, measurable target to aim at.

## What we want to study next

The score drop is only the starting point. It opens a set of sharper questions, each of which we can study with synthetic data and each of which connects to existing research:

- Is the test fair? We build the patient record from the same question and scoring guide, so the record is, by design, relevant to the question. That makes for a clean experiment, but real records are not tidied up for the question being asked. We need to study how much of the effect depends on how we create the data, and to test the AI against records that are only partly relevant, or not relevant at all.
- Different data situations. Real use is not always clean. Sometimes there is no data, sometimes the key piece is missing, sometimes the data is noisy or out of date, and sometimes it is complete and reliable. We want to check that the AI does the right thing in each case: asking when it should, and using the data when it should, instead of always doing one or the other.
- Finding the signal in a full record. So far we give the AI only the relevant facts. In reality it would receive a whole medical history, most of which has nothing to do with the current question. We want to test whether it can pick out what matters without being misled by the rest.
- Wearable sensor data. Watches and health apps produce streams of numbers over time, such as heart rate and sleep. Reading trends in this kind of data is a different and harder skill than reading a typed description, and today's text-only tests never check it. This is a key direction for a platform built around wearables.

## Relevant works

**MedAgentBench (Jan 2025):**

Clinician facing. Evaluated agents (their ability to interact with database and provide answer or interpretation). Limitations: most tasks clearly describe the data of interest, lacking evaluation of ambiguous requests.

**PhysicianBench (May 2026):**

Clinician/physician facing. Also focused on agents (their ability to interact with the EHR environment) + verifiable execution (each task decomposed into clinically meaningful milestones). Emphasis on long-horizon tasks.

Takeaway: these benchmarks are static, we can propose an “automatic framework” that augments these benchmarks with synthetic data that tackle different aspects of LLM and Agent ability (e.g., hallucination, flag conflicting data, …).

**Decomposing Physician Disagreement in HealthBench (Feb 2026):**

Physicians frequently disagree on whether a model’s response meets clinical standards. Physician disagreement sets a structural ceiling on performance. Vast majority of disagreement variance is case-specific.

(Not sure where to place this finding yet)
