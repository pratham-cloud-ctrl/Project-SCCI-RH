"""Qualify a new teacher library from frozen measured benchmark recordings."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3.motor import MotorConfig, LearnerMap, StateEstimate, control_request
from scci_rh.stage3.teacher_library import build_teacher_library
from run_stage3_studies import close_nested
from artifact_hashes import canonical_json_digest

INPUT = ROOT/'results/stage3/expert-validation'
OUT = ROOT/'results/stage3/teacher-library'
DOC = ROOT/'docs/stage3/teacher-library.md'
SOURCE_PATHS = ('src/scci_rh/stage3/teacher_library.py', 'scripts/stage3_teacher_library_study.py',
                'src/scci_rh/stage3/expert_validation.py', 'src/scci_rh/stage3/motor.py',
                'src/scci_rh/stage3/acquisition.py', 'scripts/artifact_hashes.py')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    return {path: hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for path in SOURCE_PATHS}


def load_frozen_captures():
    summary_path = INPUT/'expert-summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if summary['schema'] != 'scci_rh.stage3.expert-validation.v1':
        raise ValueError('unexpected expert benchmark schema')
    captures = []
    for entry in summary['raw_files']:
        path = INPUT/entry['path']
        if path.parent != INPUT or sha256(path) != entry['sha256']:
            raise ValueError('frozen expert recording identity failed: '+entry['path'])
        value = json.loads(gzip.decompress(path.read_bytes()).decode('utf-8'))
        if value['schema'] != 'scci_rh.stage3.expert-performance.v1':
            raise ValueError('unexpected expert recording schema')
        captures.append(value['capture'])
    return summary, captures, canonical_json_digest(summary_path)


def consumer_witness(library, config):
    # These explicit observable inputs only demonstrate the availability gate.
    # They are not a new learner calibration, delivery or learning experiment.
    estimate = StateEstimate((0., 0.), (0., 0.), 1., .001, True, 'witness', 'VALID')
    response = LearnerMap(((.06, 0.), (0., .06)), ((.001, 0.), (0., .001)),
                          .005, .001, True, (), 0, 1., 0., .001)
    rows = []
    for cadence in (1., 1.15, 1.3):
        for kind in ('learner_only', 'expert_external', 'expert_neural'):
            reference = library.reference_for(kind, cadence_hz=cadence)
            request, reason = control_request(estimate, response, reference, 1.025, config,
                                               heldout=cadence == 1.15)
            rows.append({'cadence_hz': cadence, 'kind': kind,
                         'reference_id': library.reference_id_for(kind, cadence_hz=cadence),
                         'reference_qualified': reference.qualified,
                         'qualification_reason': reference.qualification_reason,
                         'request_fraction': request.tolist(), 'policy_reason': reason})
    return {'scope': 'pure observable policy witness; no electrical pulses, delivery or learning experiment',
            'rows': rows}


def experiment():
    frozen, captures, frozen_sha = load_frozen_captures()
    config = MotorConfig(**frozen['config'])
    records = {}
    for generator in ('legacy_voluntary', 'idealized_inverse'):
        library = build_teacher_library(captures, config, generator=generator)
        records[generator] = library.to_record()
        records[generator]['consumer_witness'] = consumer_witness(library, config)
    return {'schema': 'scci_rh.stage3.teacher-library-study.v1',
            'result_id': 'SCCI_RH-S3-QUALIFIED-TEACHER-LIBRARY-1',
            'source_sha256': source_hashes(),
            'input_receipt': {'path': 'results/stage3/expert-validation/expert-summary.json',
                              'sha256': frozen_sha, 'summary_hash_scope': 'canonical parsed JSON; raw gzip hashes exact',
                              'raw_files': frozen['raw_files']},
            'scope': 'new measured teacher-library qualification; no historical result replaced',
            'historical_information_studies_replaced': False,
            'new_teacher_recordings_generated': False,
            'libraries': records}


def report(value):
    lines = ['# Measured, competence-gated teacher library', '',
             'This is a new mechanism revision, built from the separately saved',
             '[expert benchmark](expert-validation.md). It does not change the teacher or results in',
             'the historical [280-row information comparison](information-comparison.md). The old teacher',
             'failed the declared timing criterion. Its historical differences are conditional controller/',
             'plasticity outcomes, not validated expert-to-novice learning.', '',
             '## Separate admission gates', '',
             '1. **Observed competence:** every recording in a cadence domain, and the nominal training',
             '   recording, must satisfy the existing 18 mm contact spatial and 25 ms contact timing RMSE',
             '   criteria. These are kinematic peak proxies; body truth never qualifies the teacher.',
             '2. **Independent decoded representation:** the frozen voltage-feature decoder must satisfy',
             '   the same task criterion on each complete withheld recording after initial acquisition',
             '   warmup. Its externally measured residual allocation is',
             '   `2 × position RMSE + 2 × 100 ms × velocity RMSE < 25 mm`; standardized inputs must stay',
             '   within the existing ±5 range. The chronological, purged training-capture holdout must',
             '   also satisfy that allocation. The external reference does not need a neural decoder.',
             '3. **Complete trajectory representation:** the fixed nominal-trained sin/cos template must',
             '   satisfy the task criterion and `2 × measured trajectory RMSE < 25 mm` on every complete',
             '   withheld recording in the selected domain. This allocates the existing observer’s',
             '   `2 × position RMSE` term to static trajectory mismatch; no template velocity uncertainty',
             '   prediction is claimed. The thresholds were inherited before running this qualification,',
             '   not selected from its outcomes. These are empirical engineering gates, not probability',
             '   coverage or worst-case bounds. Downstream assisted prediction still needs its own gate.', '',
             'Each decoder and each external/neural template is fitted only on nominal performance0.',
             'Templates use the decoder’s same 1,757-row training partition: a chronological 75/25 split,',
             '100 ms exclusion on both sides of the split, and four-row edge trimming. The decoder’s',
             'velocity labels are differentiated and smoothed separately inside partitions. Complete',
             'other recordings remain excluded from all fitting and model/threshold selection.', '',
             '## Observed decisions', '',
             '| Generator | Cadence Hz | Observed competent recordings | Withheld recordings | External reference | Neural reference |',
             '|---|---:|---:|---:|---|---|']
    for generator, library in value['libraries'].items():
        q = library['qualification']
        for cadence, domain in q['domains'].items():
            competent = sum(row['qualification']['qualified'] for row in q['observed_competence']
                            if row['identity']['cadence_hz'] == domain['cadence_hz'])
            refs = domain['references']
            lines.append(f"| {generator} | {cadence} | {competent}/{domain['observed_recordings']} | {domain['independent_validation_recordings']} | {refs['expert_external']['qualified']} | {refs['expert_neural']['qualified']} |")
    lines += ['', '| Generator / cadence | Reference | Rejection reasons |', '|---|---|---|']
    for generator, library in value['libraries'].items():
        for cadence, domain in library['qualification']['domains'].items():
            for kind, gate in domain['references'].items():
                lines.append(f"| {generator} / {cadence} Hz | {kind} | {'; '.join(gate['reasons']) or 'qualified'} |")
    lines += ['', 'The faster task reverses direction at a nonzero position. The idealized teacher retains',
              'finite body transients rather than instantaneously jumping. A teacher can pass contact',
              'competence while the static template fails a full-trajectory allocation. Such a rejection',
              'remains visible; it is not repaired by relaxing the criterion or refitting on validation.', '',
              '| Generator | Cadence Hz | Performance | Decoder allocation mm | External template allocation mm | Neural template allocation mm |',
              '|---|---:|---:|---:|---:|---:|']
    for generator, library in value['libraries'].items():
        for row in library['qualification']['independent_validation']:
            identity, decoder, templates = row['identity'], row['decoder'], row['representations']
            allocation = decoder['error_allocation_m']
            lines.append(f"| {generator} | {identity['cadence_hz']:g} | {identity['performance_seed']} | {allocation*1000:.3f} | {templates['expert_external']['position_error_allocation_m']*1000:.3f} | {templates['expert_neural']['position_error_allocation_m']*1000:.3f} |")
    lines += ['', '## Resource and source limits', '',
              'Each generator uses eight existing 12 s recordings: **96 s total**, comprising one 12 s',
              'training capture and **84 s of withheld recordings** (36 s nominal and 48 s faster). There',
              'are four observation-noise identities per cadence, paired between cadences; faster',
              'performance0 shares the training noise identity but its trajectory/cadence is withheld.',
              'Thus 84 s is independent recording/cadence exposure, not seven independent subjects or',
              'seven unique noise identities. External and neural references receive the same measured',
              'expert resource budget. The training capture has 1,757 fit and 568 purged holdout rows.', '',
              'All recordings share one artificial subject and contact geometry. Qualified nominal',
              'references do not establish between-person decoding, transfer to other tasks/cadences,',
              'changed electrodes, real spinal signal content, retained learner benefit, or electrical',
              'delivery. The inverse generator uses the private expert movement time constant to create',
              'synthetic skill (`voluntary = desired + tau × desired velocity`). That privilege remains',
              'explicit; the library and controller receive only measured voltage features, external',
              'measurements and source identity. They receive no expert tau, voluntary coefficients,',
              'private evaluator or future online body state. Offline derivative labels are allowed',
              'within the disjoint training/validation recordings; they are not online predictors.', '',
              '**Admission is within the frozen capture model.** Its moving source is held for each',
              '5 ms acquisition block. Aperture-resolved source fidelity remains unqualified; nominal',
              'reference admission does not establish the full embodied acquisition chain. This limit',
              'is machine-readable as `source_hold_fidelity_qualified: false`. A new aperture-resolved',
              'capture revision would require fresh measured qualification rather than inheriting these',
              'admissions or changing the frozen recordings.', '',
              '## Consumer contract', '',
              '`build_teacher_library(captures, config, generator=...)` returns a `TeacherLibrary`.',
              '`library.references` is the nominal 1 Hz mapping of the existing frozen',
              '`ExpertRepresentation` type. Consumers of another cadence must call',
              '`library.reference_for(kind, cadence_hz=...)`; unsupported cadences return an explicit',
              'unqualified reference. Rejected references retain coefficients and reasons for inspection,',
              'but `control_request` returns zero with `UNAVAILABLE_EXPERT_REPRESENTATION`. External',
              'data never substitutes under an expert-neural label. The declared `learner_only` goal',
              'remains separate from expert evidence. Consumers must retain `library.library_id` and',
              '`reference_id_for(...)` in their new study provenance and honor the selected cadence gate.', '',
              'The saved pure-policy witnesses test availability behavior only. They are not new learner',
              'calibration, pulse-delivery or retained-learning experiments. A newly qualified reference',
              'is a prerequisite for revised coupled studies, not proof of their outcome.', '',
              '## Reproduction', '',
              '`python -X utf8 scripts/stage3_teacher_library_study.py --check` verifies all 16 frozen',
              'gzip input identities, refits and independently validates the two libraries, and compares',
              'the resulting receipts and this report (relative tolerance 2e-8, absolute 1e-11).',
              'Result schema: `scci_rh.stage3.teacher-library-study.v1`; each library is',
              '`scci_rh.stage3.teacher-library.v1`. Raw benchmark recordings remain under',
              '`results/stage3/expert-validation/`; no new recordings or historical replacements occur.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    value = experiment()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT/'teacher-library-summary.json'
    if args.check:
        close_nested(value, json.loads(target.read_text(encoding='utf-8')))
        for generator, library in value['libraries'].items():
            close_nested(library, json.loads((OUT/(generator+'.json')).read_text(encoding='utf-8')))
        assert DOC.read_text(encoding='utf-8') == report(value), 'teacher library report drift'
        print('Measured teacher libraries and unavailable-reference witnesses: reproduced')
    else:
        target.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        for generator, library in value['libraries'].items():
            (OUT/(generator+'.json')).write_text(json.dumps(library, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        DOC.write_text(report(value), encoding='utf-8')
        print('Measured teacher libraries and unavailable-reference witnesses: written')
    for generator, library in value['libraries'].items():
        print(generator+': '+library['library_id'])
        for cadence, domain in library['qualification']['domains'].items():
            print(cadence+' Hz: '+str({kind: gate['qualified'] for kind, gate in domain['references'].items()}))


if __name__ == '__main__':
    main()
