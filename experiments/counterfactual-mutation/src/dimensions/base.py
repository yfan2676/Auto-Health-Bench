#!/usr/bin/env python3
"""The Dimension interface — one controlled task variable we mutate and test for locality.

A dimension knows how to (1) DETECT items it can edit, (2) generate the K sweep VALUES,
(3) EDIT a conversation to one value (the single-dimension counterfactual), and (4) write
the a-priori FOOTPRINT-classifier prompt keyed to itself. Everything downstream — the fresh
answers (answers.py), the K-way grading (sweep_grade.py), the metrics (analyze.py), and the
viewer — is dimension-agnostic and works off the shortlist's `dimension` field.

Methods operate on the shortlist row `s` (so each dimension stashes whatever fields it needs
in `detect`) and the loaded example `ex` (with `messages` and parsed `rubrics`).
"""


class Dimension:
    name = "base"

    def detect(self, ex):
        """Return a dict of shortlist fields if `ex` is FIT for this dimension, else None.
        Must include at least: dimension (==self.name), base_value, label. Cheap detectors
        (regex) should gate any LLM confirm so we don't call a model on every example."""
        raise NotImplementedError

    def values(self, s):
        """The K~3 swept instantiations (e.g. ages, or data-encoding styles) for row `s`."""
        raise NotImplementedError

    def edit_one(self, messages, s, value):
        """Produce one single-dimension edit of `messages` to `value`. Returns a dict:
            {messages_var, replacements:[{find,replace}], n_applied, extra:{...}}
        `extra` carries dimension-specific metadata (e.g. fact_preserved for disclosure)."""
        raise NotImplementedError

    def footprint_prompt(self, ex, s, values):
        """The a-priori per-criterion classifier prompt keyed to this dimension. Must ask for
        JSON {"predictions":[{"idx","bucket","sensitive","reason"}], "proposed_induced":[...]}."""
        raise NotImplementedError

    def buckets(self):
        """The allowed footprint buckets for this dimension (validated in footprint.py)."""
        raise NotImplementedError
