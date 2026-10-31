# Data field dictionary

Project technical specification · Version metadata-fields/1 · 2026-10-31 · Design contract

This dictionary defines cross-species electrophysiology metadata. Representable data are not necessarily executable inputs; the new fields are not yet integrated as a whole into intake forms or the runtime API.

[General requirements](/standards/overview) · [Method applicability](/standards/applicability) · [Current implementation](/standards/implementation)

## 1 Organization and scope

Five groups describe the subject, signal/files, channels/acquisition, experiment/state, and processing/provenance. Scope identifies the subject, acquisition session, recording, independent stream, channel, electrode contact, comparison group, time interval or analysis selection. Session-level context must not overwrite channel- or interval-specific facts.

Channel counts derive from channel collections; age groups derive from age and declared species-specific rules. Format, species, recording site, signal object and hardware technology are independent. Add method prerequisites without creating species-by-disease-by-format categories.

## 2 Common value contract

Each value carries value, status, source and confirmation. known means explicitly declared, not independently proven; unknown means missing or unextracted; not_applicable requires a reason; conflict retains source alternatives and must not silently select one for execution. The normalized value is null for unknown, not_applicable and conflict.

source records kind (file_header, sidecar, provider_document, manual or derived), reference and field locator; derived values also retain transformation and version. confirmation is unreviewed or confirmed and does not establish clinical or experimental truth. Empty lists establish absence only within an explicitly inspected scope.

Missing actions are method-scoped: block_reading prevents reliable decoding; block_registration prevents a stable record identity; block_execution prevents execution of the requested selection; restrict_method disables dependent methods only; restrict_interpretation limits interpretation; retain_unknown preserves missing context. These are design requirements; current behavior is listed separately.

qc_use is reader, routing, technical, context or provenance. Context fields support interpretation and validation strata; they must not automatically alter thresholds, scores or cleaning without independent validation.

## 3 Age and species

Age retains lower/upper bounds, day/week/month/year unit, birth/gestational/other/unknown reference, recording/session_start/experiment_start/source_unspecified time context, and source_text. Exact ages have equal bounds; a missing bound is null, but both cannot be missing. Bounds are nonnegative and ordered. Preserve months and years rather than inventing exact day conversions.

Gestational ages retain the source definition of their origin; do not conflate postnatal, gestational and corrected age. A life_stage-only declaration is allowed. Do not invent cross-species adult cutoffs. Missing species remains unknown; compatibility defaults from external formats are recorded as defaults, not confirmed facts.

## 4 Subject

| Field | Definition and value type | Scope | Missing action | Use |
| --- | --- | --- | --- | --- |
| `subject.id` · Subject identifier | De-identified source subject ID; matching names across datasets do not establish identity. `string` | `subject` | `retain_unknown` | `provenance` |
| `subject.species` · Species | Preserve source species text; map a scientific name and taxonomy ID only with evidence, never assume human. `taxon` | `subject` | `restrict_interpretation` | `context` |
| `subject.age` · Source age | Value or interval, unit, reference event and time context; age at experiment start is not exact age at this session. `age` | `session` | `restrict_interpretation` | `context` |
| `subject.life_stage` · Life stage | Source-declared or derived under an explicit species-specific rule; retain rule version, do not infer numeric age. `stage` | `session` | `retain_unknown` | `context` |
| `subject.sex` · Biological sex | Retain the source definition and value; missing does not identify a sex. `string` | `subject` | `retain_unknown` | `context` |
| `subject.strain` · Strain and genotype | Record animal strain and genotype separately; unknown must not become wild type. `object` | `subject` | `retain_unknown` | `context` |
| `subject.background` · Disease or animal model | Multiple sourced backgrounds are allowed; healthy control requires evidence, treatment is not automatically disease. `array` | `session` | `restrict_interpretation` | `context` |

## 5 Signal and files

| Field | Definition and value type | Scope | Missing action | Use |
| --- | --- | --- | --- | --- |
| `recording.id` · Recording identifier | Stable ID for this source or derived recording, distinct from subject ID. `string` | `recording` | `block_registration` | `provenance` |
| `recording.files` · Files and companions | Main file, companions, format, digest algorithm and value; format does not establish modality. `array` | `recording` | `block_reading` | `reader` |
| `recording.signal_kind` · Signal object | continuous_voltage, epoched_voltage, sorted_units, derived_feature or unknown; representability is not execution support. `string` | `stream` | `restrict_method` | `routing` |
| `recording.recording_site` · Recording site | scalp, cortical_surface, depth, other or unknown; one file may contain multiple groups. `string` | `channel_group` | `restrict_method` | `routing` |
| `recording.streams` · Signal streams | Stable stream IDs, source object paths and channel maps; do not concatenate by default. `array` | `recording` | `block_reading` | `reader` |
| `recording.sampling_rate_hz` · Sampling rate | Native rate in Hz; preserve disagreement between header and timestamps, do not average it away. `positive_number` | `stream` | `restrict_method` | `technical` |
| `recording.sample_count` · Sample count | Actual samples per stream, not inferred from rounded duration. `nonnegative_integer` | `stream` | `block_reading` | `technical` |
| `recording.duration_seconds` · Duration | Store file and declared experimental duration separately in seconds; padding is not observed experimental time. `nonnegative_number` | `stream` | `restrict_method` | `technical` |
| `recording.clock` · Native clock | Source first sample, time origin, timestamps or rate and reference; retain nonzero origins. `clock` | `stream` | `restrict_method` | `technical` |
| `recording.continuity` · Continuity | continuous, epoched, discontinuous or unknown, with known segments and gaps. `object` | `stream` | `restrict_method` | `technical` |
| `recording.selection` · Analysis selection | Selected stream, source channels and half-open sample interval; changed selection requires a new plan. `selection` | `analysis` | `block_execution` | `routing` |

## 6 Channels and acquisition

| Field | Definition and value type | Scope | Missing action | Use |
| --- | --- | --- | --- | --- |
| `acquisition.channels` · Channel identities and roles | Stable ID, source index/name, declared type and confirmed role; duplicate names stay distinct and digital sync is not neural voltage. `array` | `channel` | `block_execution` | `technical` |
| `acquisition.calibration` · Units and calibration | Source unit, scale/offset, physical unit, evidence and confidence; unknown units disable absolute-amplitude criteria. `calibration` | `channel` | `restrict_method` | `technical` |
| `acquisition.reference` · Reference and comparison groups | Separate acquisition reference, current reference and comparable groups; ECG/EOG auxiliary channels are not reference electrodes. `object` | `channel_group` | `restrict_method` | `technical` |
| `acquisition.electrodes` · Electrode contacts | Contact IDs, channel-to-contact mapping and positive/negative contacts; contact count is not channel count. `array` | `electrode` | `restrict_method` | `technical` |
| `acquisition.coordinates` · Positions and coordinate frame | Coordinate values, units, frame and measured/template provenance are inseparable; missing positions disable spatial operations. `coordinates` | `electrode` | `restrict_method` | `technical` |
| `acquisition.hardware` · Acquisition hardware | Manufacturer, model, technology and evidence; Neuropixels is a technology/device, not a species or format. `object` | `stream` | `restrict_method` | `routing` |
| `acquisition.probe_layout` · Probe layout and groups | Sourced probe, shank, site, grid or shaft relations; names alone do not establish adjacency. `object` | `channel_group` | `restrict_method` | `technical` |
| `acquisition.filters` · Acquisition filters and bandwidth | Hardware/acquisition software filters and parameters; unknown is distinct from explicitly unfiltered. `array` | `stream` | `restrict_method` | `technical` |
| `acquisition.line_frequency_hz` · Power-line frequency | Declared mains frequency such as 50/60 Hz; distinguish a measured spectral peak from a supply declaration. `positive_number` | `session` | `restrict_method` | `technical` |

## 7 Experiment and state

| Field | Definition and value type | Scope | Missing action | Use |
| --- | --- | --- | --- | --- |
| `experiment.task` · Recording task | Task ID, name and source; multiple tasks in one session need intervals. `object` | `session` | `retain_unknown` | `context` |
| `experiment.states` · State intervals | Record wake, sleep and anesthesia with clocked intervals; coarse session declarations also state coverage. `array` | `interval` | `restrict_interpretation` | `context` |
| `experiment.events` · Events and annotations | Source label, time/sample, duration, clock and mapping; point events do not acquire invented duration. `array` | `interval` | `restrict_method` | `technical` |
| `experiment.annotation_coverage` · Annotation extraction status | Distinguish not extracted, checked absent, partially extracted and extracted scope; an empty list alone does not prove absence. `object` | `stream` | `restrict_interpretation` | `provenance` |

## 8 Processing and provenance

| Field | Definition and value type | Scope | Missing action | Use |
| --- | --- | --- | --- | --- |
| `processing.derivation` · Raw/derived relationship | Processing status, parent recording and relationship; unknown history does not establish raw data. `object` | `recording` | `restrict_interpretation` | `provenance` |
| `processing.history` · Processing history | Ordered filtering, re-referencing, resampling, interpolation, ICA/ASR with parameters, scope and software versions. `array` | `stream` | `restrict_method` | `technical` |
| `processing.source` · Source and version | Source URL/DOI, fixed version, license and conflicts; separate source declarations from platform decisions. `object` | `recording` | `restrict_interpretation` | `provenance` |
| `processing.revision` · Descriptor revision | Dictionary version, descriptor revision and parent; historical jobs retain their original description. `object` | `recording` | `block_registration` | `provenance` |

## 9 Compound value structures

The following summaries describe values; field instances still follow the provenance/status contract in section 2. Preserve original source text.

| Type | Structure |
| --- | --- |
| `string` | `string` |
| `object` | `object` |
| `array` | `array` |
| `positive_number` | `finite number > 0` |
| `nonnegative_number` | `finite number >= 0` |
| `nonnegative_integer` | `integer >= 0` |
| `taxon` | `{source_label, scientific_name?, taxonomy_id?}` |
| `age` | `{lower?, upper?, unit, reference, at, source_text}; bound required; lower <= upper; exact when equal` |
| `stage` | `{label, source_declared, rule_id?, rule_version?}; derived stage requires rule and known species` |
| `clock` | `{reference, first_sample?, origin_seconds?, rate_hz?, timestamps_reference?}; per-stream native time` |
| `selection` | `{stream_id, source_indices, start_sample, stop_sample_exclusive}; nonempty interval` |
| `calibration` | `{source_unit, physical_unit, scale, offset, mapping}; physical = stored * scale + offset` |
| `coordinates` | `{values, unit, frame, provenance}; values must reference stable electrode IDs` |

## 10 Maintenance and mapping

The authoritative catalog is specs/metadata-fields.v1.json; scripts/build_metadata_dictionary.py generates both languages. Changes to IDs, meaning, units, scope or missing semantics require a dictionary version and migration record. Runtime API mappings require separate implementation and tests; this catalog is not an accepted upload JSON schema.

BIDS mappings distinguish participants, recording JSON, channels, electrodes, coordsystem and events. NWB mappings distinguish Subject, ElectricalSeries, electrodes, devices and time objects. Preserve source values with explicit limits when a mapping is incomplete.

[BIDS 1.11.2](https://bids-specification.readthedocs.io/en/v1.11.2/) · [NWB 2.11.0](https://github.com/NeurodataWithoutBorders/nwb-schema/blob/2.11.0/core/nwb.file.yaml)
