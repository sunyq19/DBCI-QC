# EEG QC evidence and applicability

Informative document · evidence/1 · Verified: 31 October 2026

[Scalp EEG specification](/en/standards) · [Workbench](/en)

This page provides traceable sources for the DBCI-QC project specification. The specification is a consultation draft, not a published national, industry or association standard. Sources retain their original scope; adopting a field or method does not establish compliance with an entire external standard.

## 1 Evidence types

| Type | Purpose | Citation rule |
| --- | --- | --- |
| Industry standard | Dataset descriptions, acquisition, annotation and traceability | Retain status, scope and clause; future requirements are prospective references |
| Expert guideline or association document | Clinical acquisition, reporting and expert assessment | Retain the clinical setting and recommendation strength |
| Data specification | Field semantics, organization and interoperability | Separate structural conformity from signal quality |
| Method paper, author manual or official API | Measurements, algorithm assumptions and implementation provenance | Defaults are not industry acceptance limits; published accuracy is not platform accuracy |
| Project convention | Coordinates, states, coverage, configuration and reporting | Identify it as a project rule and verify it with reproducible examples and tests |

The `SRC-*` identifiers below are stable references for rules, modules and reports. M01–M09 are project implementation mappings, not clauses of the external sources. A citation does not establish implementation; see [implementation scope](/en/standards/implementation).

## 2 Evidence index

| Identifier | Source | Main mapping |
| --- | --- | --- |
| [SRC-1833](#src-1833) | YY/T 1833.2—2022 | Identity, purpose, acquisition basis, annotation, traceability; M01, M02, M07, M09 |
| [SRC-2029](#src-2029) | YY/T 2029—2026 | Electrodes, sampling, filters, noise and versions; M01–M07, M09 |
| [SRC-CAAE](#src-caae) | CAAE 2022 expert guidelines | Clinical context and report structure; M02, M07, M09 |
| [SRC-CAAE-QC](#src-caae-qc) | CAAE 2024 QC programme | Separate recording/report assessment and expert review; M08, M09 |
| [SRC-IFCN](#src-ifcn) | IFCN/ILAE 2023 guidelines | Routine and sleep clinical recording; M01, M02 |
| [SRC-BIDS](#src-bids) | BIDS EEG 1.11.2 | Channels, electrodes, reference, sampling, filtering; M01, M02, M07 |
| [SRC-PREP](#src-prep) | PREP 2015 | Nonfinite, flat, amplitude, correlation and noise indicators; M03, M05 |
| [SRC-FASTER](#src-faster) | FASTER 2010 and author manual | Statistical channel screening; current extension M05 |
| [SRC-AR](#src-ar) | Autoreject 2017 | Epoch peak-to-peak measurements and cross-validated thresholds; current extension M03 |
| [SRC-SCIPY](#src-scipy) | Official SciPy Welch API | PSD measurement; M04 |
| [SRC-FOOOF](#src-fooof) | Donoghue et al. 2020 and FOOOF API | Aperiodic background and spectral peaks; M04 |
| [SRC-BRAINELECQC](#src-brainelecqc) | Pinned BrainElecQC source | Integrity, line-noise testing, band integration and combined high-frequency screening; M03–M06 |
| [SRC-MNE](#src-mne) | Official MNE APIs | PSD, bridging, LOF and auxiliary events; M04–M06 |
| [SRC-PROJECT](#src-project) | DBCI-QC conventions | States, original coordinates, denominators, reports and review; M01–M09 |

## SRC-1833

**YY/T 1833.2—2022, Artificial intelligence medical device — Quality requirements and evaluation — Part 2: General requirements for datasets** (English descriptive translation). The official catalogue lists it as current, effective 1 July 2023.

- **Location:** §§4.1.1–4.1.4, printed pp.3–4 / PDF pp.7–8; §5.2.11, printed pp.8–9 / PDF pp.12–13. Short original excerpt, §4.1.4.3: “标注分歧的仲裁机制” (arbitration of annotation disagreements).
- **Use:** Dataset descriptions, provenance, processing, annotation and traceability.
- **Limit:** Its scope is AI medical-device datasets. It does not prescribe EEG bad-channel algorithms or universal quality scores. Hashes and run IDs are project implementation choices.

[Official catalogue](https://hbba.sacinfo.org.cn/stdDetail/ad8c7508b67bea44c82a1d0dd7f749d35b7b258990738862da863ef34317ad30) · [Official text](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2022/20220720/YYT183322022.pdf)

## SRC-2029

**YY/T 2029—2026, EEG dataset quality requirements and evaluation for AI algorithms in BCI medical devices** (English descriptive translation). Published 24 August 2026; effective 1 September 2027. The catalogue currently marks it as forthcoming.

- **Location:** §§5.1–5.2.9, printed pp.2–3 / PDF pp.8–9; §§6.5, 7.4, 7.7, 8.2.2, printed pp.7–10 / PDF pp.13–16. §5.2.6 refers to the responsible party’s “声称值” (declared value).
- **Use:** Prospective acquisition, noise-measurement, annotation and versioning reference.
- **Limit:** No universal line-noise ratio or bad-channel boundary. The platform’s high-frequency power ratio is not automatically the specified band-limited RMS noise measurement.

[Official catalogue](https://hbba.sacinfo.org.cn/stdDetail/866eaadd4e5c255fdb8e12030faa6b574a71658ab56fa22d356104c3561fd11b) · [Official text](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2026/2026-10/2c9048cca08f981001a12512f7a54d97.pdf)

## SRC-CAAE

**CAAE 2022 clinical EEG technical expert guidelines**, Journal of Epilepsy 8(1).

- **Location:** Guideline IX §§1–3, journal pp.38–39 / PDF pp.37–38; introduction: “全面、简要和有重点” (comprehensive, concise and focused). Acquisition parameters: Guideline I §2.7; recording information: Guideline IX §§1.5–1.6.
- **Use:** Structured acquisition, context, state and event descriptions.
- **Limit:** A research QC report does not become a clinical diagnosis. Do not cite 2022 guideline clauses as clauses of the 2026 association standard.

[Official association text](https://www.caae.org.cn/Public/Uploads/20220118/video/61e6242d78ca7.pdf)

## SRC-CAAE-QC

**CAAE EEG QC programme**, document 〔2024〕11, 25 March 2024.

- **Location:** Parts II–III, PDF pp.3–4; excerpt: “复核和内控机制” (review and internal-control mechanisms). It identifies nine report-quality and seven recording-quality items.
- **Use:** Separate assessment of recording and report quality, with expert sampling and review.
- **Limit:** This association programme is not an automatic scoring rubric. Its item list does not supply weights, a 0–100 score or universal artifact thresholds.

[Association entry](https://www.caae.org.cn/news/show/id/539) · [Official PDF](https://www.caae.org.cn/ueditor/php/upload/file/20240325/1711335645879652.pdf)

## SRC-IFCN

**Peltola et al., 2023, IFCN/ILAE minimum standards for routine and sleep EEG**.

- **Location:** §3.2, Table 3, §3.3.1; excerpt: “our recommendations are conditional”. Section references avoid mixing pagination between the two journals.
- **Use:** Clinical acquisition context: electrodes, auxiliary channels, sampling and duration. The 256 Hz recommendation is contextual; 0.5–70 Hz refers to display filtering.
- **Limit:** These are not universal rejection criteria for research excerpts, sparse sleep EEG or invasive recordings. Display recommendations do not require modification of original data.

[Clinical Neurophysiology publication](https://doi.org/10.1016/j.clinph.2023.01.002) · [Epilepsia publication](https://doi.org/10.1111/epi.17448) · [Author manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC10006292/)

## SRC-BIDS

**BIDS EEG, pinned version 1.11.2**.

- **Location:** EEG terminology, Sidecar JSON, Channels description and Electrodes description; requirement levels checked against the versioned schema.
- **Use:** Separate electrodes from sampled channels. The EEG reference, sampling frequency, power-line frequency and software filters are required for the corresponding BIDS object; channel tables require `name/type/units`.
- **Limit:** Structural validation does not establish signal quality. Missing BIDS metadata does not necessarily mean a native file is corrupt; source channel status is not automatically independent QC ground truth.

[Versioned chapter](https://github.com/bids-standard/bids-specification/blob/v1.11.2/src/modality-specific-files/electroencephalography.md) · [Sidecar requirements](https://github.com/bids-standard/bids-specification/blob/v1.11.2/src/schema/rules/sidecars/eeg.yaml) · [Channel requirements](https://github.com/bids-standard/bids-specification/blob/v1.11.2/src/schema/rules/tabular_data/eeg.yaml)

## SRC-PREP

**Bigdely-Shamlo et al., 2015, The PREP pipeline**.

- **Location:** Abstract and “Detecting noisy or outlier channels”; excerpt: “identification of noisy channels depends on the reference”.
- **Use:** Reference-dependent amplitude, correlation, prediction, noise and numerical-integrity indicators.
- **Limit:** The platform’s basic nonspatial implementation comes from BrainElecQC, not the complete PREP/PyPREP pipeline. Published parameters and accuracy do not establish platform performance; actual filters, quantiles and comparison groups require separate documentation.

[Original paper](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2015.00016/full) · [Original MATLAB project](https://github.com/VisLab/EEG-Clean-Tools) · [Pinned BrainElecQC implementation](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/bad_channels.py)

The [12 October 2026 correction](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2026.2015651/full) updates code access and availability statements, not channel criteria.

## SRC-FASTER

**Nolan, Whelan and Reilly, 2010, FASTER**; author manual v1.2.3, distributed with v1.2.3b.

- **Location:** Paper abstract; manual PDF p.15, “Channel rejection”; p.32, FAQ and scripting. Excerpt: “It has not been tested on fewer than 32 channels”.
- **Use:** Statistical outlier screening and explicit feature/parameter choices.
- **Limit:** The paper’s full text was unavailable; procedural details use the author manual. MNE-FASTER is a Python implementation, not the original MATLAB pipeline. The adapter’s eight-channel gate is not published validation of eight-channel data; z=3 is not an industry limit.

[Paper abstract](https://pubmed.ncbi.nlm.nih.gov/20654646/) · [Author distribution](https://sourceforge.net/projects/faster/files/) · [Author manual](https://downloads.sourceforge.net/project/faster/FASTER%20manual.pdf)

## SRC-AR

**Jas et al., 2017, Autoreject: Automated artifact rejection for MEG and EEG data**.

- **Location:** Author version v3, §2.1 equations (1)–(4), §2.2 and §3; global-method excerpt: “same threshold for all sensors”.
- **Use:** Epoch peak-to-peak measurements, cross-validated thresholds and declared fitting/evaluation scope.
- **Limit:** Global estimation and local thresholds/interpolation are different capabilities. Fixed-window screening is not task-trial validity or evidence that local cleaning is implemented. Estimated thresholds are data-dependent, not universal amplitude limits.

[Publication](https://doi.org/10.1016/j.neuroimage.2017.06.030) · [Author text v3](https://arxiv.org/html/1612.08194v3) · [Global API](https://autoreject.github.io/stable/generated/autoreject.get_rejection_threshold.html) · [Local API](https://autoreject.github.io/stable/generated/autoreject.AutoReject.html)

## SRC-SCIPY

**Official SciPy `signal.welch` API and Welch (1967)**. The API page showed SciPy 1.18.0; runtime versions are recorded separately.

- **Location:** API description, `scaling`, `average` and Notes; excerpt: “averaging the periodograms”. Original method: IEEE Transactions on Audio and Electroacoustics 15(2):70–73.
- **Use:** Explicit windows, segments, overlap, detrending and averaging. With V and Hz input, density is V²/Hz, distinct from a V² power spectrum.
- **Limit:** Four-second windows are wrapper choices, not acceptance criteria. Frequency-bin spacing is not universally identical to spectral resolving ability.

[Official API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html) · [Welch paper DOI](https://doi.org/10.1109/TAU.1967.1161901)

## SRC-FOOOF

**Donoghue et al., 2020, Parameterizing neural power spectra into periodic and aperiodic components**, Nature Neuroscience 23:1655–1665; FOOOF 1.1.1 API.

- **Location:** Methods, “Algorithmic parameterization”; Discussion; API Notes and attributes. Excerpt: “putative periodic oscillatory peaks”.
- **Use:** Separate background and above-background peaks, preserving model settings and fit error. Inputs are linear frequency/power; modelling uses log10 power.
- **Limit:** Peak height differs from background-inclusive alpha integration. Fit quality is not recording quality; peaks do not necessarily establish oscillations. Fixed mode and fitting gates are project choices.

[Publication](https://doi.org/10.1038/s41593-020-00744-x) · [Author manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC8106550/) · [FOOOF API](https://fooof-tools.github.io/fooof/generated/fooof.FOOOF.html)

## SRC-BRAINELECQC

**BrainElecQC, pinned commit `f007d829712d1b824cda79409d181a3313d6a78f`**, the direct source of the platform’s basic methods.

| Source location | Used behavior | Evidence type |
| --- | --- | --- |
| [`continuity.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/continuity.py), `ContinuityConfig` and calibration classification | Nonfinite samples, equality runs, near-zero and endpoint plateaus | Implementation rules, not universal clinical thresholds |
| [`spectral.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/spectral.py), [`alpha_power.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/alpha_power.py) | Welch wrapper, DPSS/F test, multiple-testing correction and integration | [Chronux `ftestc`](https://chronux.org/chronuxFiles/Documentation/chronux/spectral_analysis/continuous/ftestc.html) is a methodological reference, not a direct dependency; actual scan/correction scope follows this implementation |
| [`bad_channels.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/bad_channels.py) | Nonspatial PREP components | Distinct from complete PREP; see SRC-PREP |
| [`events.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/events.py), [`muscle.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/muscle.py) | EEG time-locked summaries, joint high-frequency conditions and EMG corroboration | Uses MNE primitives; not the original `annotate_muscle_zscore` detector |

Pinned code establishes implementation provenance, not industry consensus or independent clinical validation.

## SRC-MNE

**Official MNE API documentation**. Pages showed 1.13.2 when checked; this does not identify the runtime package version.

| Official API and location | Supported definition | Limit |
| --- | --- | --- |
| [`psd_array_welch`, Parameters / Returns](https://mne.tools/stable/generated/mne.time_frequency.psd_array_welch.html) | Welch segments, windows, overlap, FFT and aggregation | PSD does not establish an EEG acceptance boundary; preserve actual parameters and power units |
| [`compute_bridged_electrodes`, Parameters / Returns](https://mne.tools/stable/generated/mne.preprocessing.compute_bridged_electrodes.html) | Variance of channel differences, electrical distance and channel pairs | `lm_cutoff` bounds the local-minimum search; do not present it as a returned final boundary |
| [`find_bad_channels_lof`, threshold](https://mne.tools/stable/generated/mne.preprocessing.find_bad_channels_lof.html) | Distance-based channel outlier factor | Threshold is a “hyperparameter to optimize”; default 1.5 is not an industry standard |
| [`find_eog_events`](https://mne.tools/stable/generated/mne.preprocessing.find_eog_events.html) / [`find_ecg_events`](https://mne.tools/stable/generated/mne.preprocessing.find_ecg_events.html), Returns | Auxiliary eye/heartbeat event locations | An auxiliary event alone does not demonstrate EEG contamination; supporting evidence is required |
| [`annotate_amplitude`](https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html) / [`annotate_muscle_zscore`](https://mne.tools/stable/generated/mne.preprocessing.annotate_muscle_zscore.html), Parameters / Returns | Optional adjacent-difference and across-channel high-frequency screening | Report separately from BrainElecQC constant-run and combined high-frequency methods |

API documentation describes behavior, not platform accuracy. Reports separately identify actual package versions, parameters, applicability and source identities.

## SRC-PROJECT

**DBCI-QC project conventions**, defined in the [general specification](/en/standards/overview), [field dictionary](/en/standards/fields), [applicability rules](/en/standards/applicability) and module descriptions.

Stable record/candidate IDs, original sample coordinates, coverage denominators, interval deduplication, separate unassessed/no-candidate states, frozen configurations, HTML/JSON consistency and separate human review records are project contracts. They are not verbatim requirements of the sources above.

Nonfinite values, numerical flatness, endpoint plateaus and high-frequency ratios each require an explicit implementation source and project parameters. A rule without an external numerical basis remains a project rule; a bibliography cannot substitute for threshold validation. Cross-record comparisons and aggregate scores additionally require calibration and intended-use validation.

The pooled candidate fractions, configurable weighted mean and whole-record pooling in [EEG project scoring](/en/standards/eeg-scoring) are project conventions. PREP, HAPPE and external standards do not prescribe or validate this equation.

## 3 Verification level and versions

- Both YY/T catalogue entries were checked again. Clause locations were checked against archived official NIDC PDFs. CAAE pages returned HTTP 502 during this verification; archived official association PDFs were used, without claiming a fresh download.
- The [official T/CAAE 002—2026 catalogue](https://www.ttbz.org.cn/standardDetail/3dbp0828nk5v40yqbkss6m7m651q4sj.html) lists it as current, effective 6 February 2026. Its formal full text was not obtained, so it receives no criterion-level evidence ID. Equivalence to the 2022 expert guidelines is not assumed.
- IFCN/ILAE, PREP and Autoreject texts and official API pages were checked online. FASTER was checked through its abstract and archived author manual. BIDS uses pinned source and schemas rather than guessing unexpanded documentation macros.
- Only short excerpts, locations and links are included; external standards are not redistributed in the repository. SHA-256 identifies the reviewed archive, not publisher endorsement.

| Archived document | SHA-256 |
| --- | --- |
| YY/T 1833.2—2022 PDF | `ea6ddb9169c3685e16f6faa607b8d284a94675ccfb06c1bc3787cdcb505efb40` |
| YY/T 2029—2026 PDF | `cfaabe9e6202a9f06fe90aa16a1837f9c39ab65e150a0913dfea76e76b10bfac` |
| CAAE 2022 guidelines PDF | `68a9d87e194b6d17bd7d8685469194ad16e5cd06d268b35321818394af1e55a2` |
| CAAE 2024 QC programme PDF | `8375dc49108d0fbe13d54d57b3eb1ab1fcf720cd6c8751537e0bfe2c751bf70f` |
| FASTER author manual PDF | `2dcf3fd0c73b950a7d1e5e6d36ea468b89b7ae2adcb15bd42f43bda5365445c1` |
