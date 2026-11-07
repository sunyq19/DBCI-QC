# EEG project scoring rules

Project trial · `project-weighted/1.0` · 7 November 2026 · Not expert reviewed

## Scope

Scalp EEG currently supports three score components: integrity (M03), line-interference candidates (M04), and high-frequency bursts (M06). ECoG, sEEG and Neuropixels AP/LF currently report measurements without quality scores. Their candidate criteria have not been established for scoring. Dataset consistency and visualization do not contribute quality scores.

## Formula

```text
Component = 100 × (1 − candidate amount / assessed amount)
Total = Σ(component × weight) / Σweight
```

Integrity uses channel-samples outside the union of nonfinite and constant candidates. Line interference uses channel-windows, deduplicated across tested frequencies. High-frequency bursts use the detector's valid channel-seconds. Sum the original numerators and denominators across channels and windows before calculating fractions. Do not average window scores.

Weights range from 0 to 100; at least one must be positive. Defaults are equal weights for selected scorable modules. Zero excludes a component from the total; it does not remove its observations. A missing positive-weight component or incomplete recording coverage makes the total unavailable. Do not silently redistribute its weight. All selected channels need valid evidence. Filtered-out frequencies are not scored as clean.

Example: components 100, 60, 95 with weights 1, 2, 1 produce 78.75. Weights are frozen in `qc_config.scoring`, included in the plan fingerprint, and shown with the report. Scores only summarize selected checks, not universal usability or clinical validity. Local suspicious channels and intervals remain visible independently.

## Module contract and comparison

Each signal module declares `can_output_score` and a `scoring` record with role, component IDs, version and explanation. M03/M04/M06 provide components for scalp EEG; M08 aggregates and must not be counted again. Other modules provide evidence. Capability does not guarantee an actual score for a particular recording.

Compare only matching modalities, methods, parameters, analysis scope, processing history, score version and weights. Keep original evidence and historical reports immutable. Explicitly published score revisions identify the prior version and link to its report. Legacy versions 0.1 and 0.2 remain interpretable; new plans use this version. Threshold accuracy, weights and other-modality scoring still require representative data and expert review.
