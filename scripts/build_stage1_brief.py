"""Build the Stage 1 proposal figures and review PDF; no efficacy results."""
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak,
)

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / 'docs' / 'stage1'
FIG = DOSSIER / 'figures'
OUT = ROOT / 'output' / 'pdf' / 'SCCI_RH_stage1_system_specification.pdf'
INK = '#15293D'
BLUE = '#225B86'
TEAL = '#12756D'
AMBER = '#AD671C'
PURPLE = '#674B91'
GRAY = '#627485'


def node(ax, x, y, width, height, title, lines, color=BLUE, conditional=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), width, height, boxstyle='round,pad=0.025,rounding_size=0.10',
        facecolor='#F7FAFC', edgecolor=color, linewidth=1.7,
        linestyle='--' if conditional else '-', zorder=2,
    ))
    ax.text(x + 0.18, y + height - 0.25, title, color=color, fontsize=17,
            fontweight='bold', va='top', zorder=3)
    ax.text(x + 0.18, y + height - 0.70, '\n'.join(lines), color=INK,
            fontsize=15.5, va='top', linespacing=1.35, zorder=3)


def arrow(ax, start, end, color=GRAY, curve=0, dashed=False):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle='-|>', mutation_scale=17, linewidth=1.7,
        color=color, connectionstyle=f'arc3,rad={curve}',
        linestyle='--' if dashed else '-', zorder=1,
    ))


def figure(name, draw):
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('white')
    ax.set(xlim=(0, 14), ylim=(0, 8))
    ax.axis('off')
    draw(ax)
    plt.subplots_adjust(left=0.01, right=0.99, bottom=0.02, top=0.98)
    matplotlib.rcParams['svg.fonttype'] = 'none'
    fig.savefig(FIG / f'{name}.svg', facecolor='white')
    vector = FIG / f'{name}.svg'
    vector.write_text('\n'.join(line.rstrip() for line in vector.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    fig.savefig(FIG / f'{name}.png', dpi=220, facecolor='white')
    plt.close(fig)


def full_system(ax):
    node(ax, .3, 6.1, 4.0, 1.5, 'SCCI_RH Studio / offline',
         ['Expert representation', 'Calibration and policy versions'], PURPLE)
    node(ax, 5.0, 6.1, 4.0, 1.5, 'SCCI_RH Hub / companion',
         ['Task context and application', 'External sensing and records'], TEAL)
    node(ax, 9.7, 6.1, 4.0, 1.5, 'Selected task / endpoint',
         ['Motion, force or pressure', 'Measured functional outcome'], TEAL)
    arrow(ax, (4.35, 6.85), (4.95, 6.85), PURPLE)
    arrow(ax, (9.65, 6.85), (9.05, 6.85), TEAL)
    ax.add_patch(FancyBboxPatch((.15, 2.15), 13.7, 3.45,
                 boxstyle='round,pad=0.03', facecolor='#F0F5FA',
                 edgecolor='#B9CCDC', linewidth=1))
    ax.text(.4, 5.30, 'SCCI_RH CORE / IMPLANTED ENGINEERING PROPOSAL',
            fontsize=16, fontweight='bold', color=BLUE)
    node(ax, .4, 3.0, 4.0, 1.75, 'Recording and conversion',
         ['Protection / differential AFE', 'ADC / timestamps / validity'], BLUE)
    node(ax, 5.0, 3.0, 4.0, 1.75, 'Local compute / gate',
         ['Estimate / buffer / schedule', 'Limits and resource arbitration'], BLUE)
    node(ax, 9.6, 3.0, 4.0, 1.75, 'Monitored stimulation',
         ['Routing / programmable output', 'Current / charge / compliance'], BLUE)
    arrow(ax, (4.45, 3.88), (4.95, 3.88), BLUE)
    arrow(ax, (9.05, 3.88), (9.55, 3.88), BLUE)
    arrow(ax, (7, 6.05), (7, 4.80), BLUE)
    ax.text(7, 5.70, 'versioned commands + telemetry', fontsize=12.5,
            color=GRAY, ha='center', backgroundcolor='white')
    ax.text(.45, 2.50, 'Power / storage or transfer / independent supervisor / link integrity',
            fontsize=16, color=BLUE)
    node(ax, .4, .20, 4.0, 1.4, 'Spinal recording access',
         ['Target-specific neural mixture'], AMBER, True)
    node(ax, 5.0, .20, 4.0, 1.4, 'Accessible circuit + body',
         ['Uncertain recruitment / response'], AMBER, True)
    node(ax, 9.6, .20, 4.0, 1.4, 'Stimulation access',
         ['Target-specific contact geometry'], AMBER, True)
    arrow(ax, (2.4, 1.65), (2.4, 2.95), TEAL)
    arrow(ax, (11.6, 2.95), (11.6, 1.65), BLUE)
    arrow(ax, (9.55, .9), (9.05, .9), AMBER)
    arrow(ax, (4.95, .9), (4.45, .9), AMBER)
    ax.plot([9.05, 9.3, 13.92, 13.92, 13.35], [1.3, 1.8, 1.8, 5.8, 5.8],
            color=TEAL, linewidth=1.7, zorder=1)
    arrow(ax, (13.35, 5.8), (13.35, 6.05), TEAL)
    ax.text(13.6, 1.95, 'feedback', fontsize=12.5, color=TEAL,
            ha='right', backgroundcolor='white')


def expert_learning(ax):
    node(ax, .3, 6.0, 4.1, 1.65, '1 / Expert performance',
         ['Spinal samples + context', 'Task events and outcome labels'], PURPLE)
    node(ax, 4.95, 6.0, 4.1, 1.65, '2 / Learned representation',
         ['Task-related neural features', 'Held-out predictive value'], PURPLE)
    node(ax, 9.6, 6.0, 4.1, 1.65, '3 / Learner calibration',
         ['Individual response mapping', 'Uncertainty and control limits'], TEAL)
    arrow(ax, (4.45, 6.8), (4.90, 6.8), PURPLE)
    arrow(ax, (9.10, 6.8), (9.55, 6.8), PURPLE)
    node(ax, .3, 3.55, 4.1, 1.65, '6 / Active learner attempt',
         ['Movement + sensory feedback', 'Measured performance and effort'], AMBER, True)
    node(ax, 4.95, 3.55, 4.1, 1.65, '5 / Electrical intervention',
         ['Admitted / delivered output', 'Uncertain circuit recruitment'], BLUE)
    node(ax, 9.6, 3.55, 4.1, 1.65, '4 / Personalized policy',
         ['Estimated learner state', 'Expert features + goal + limits'], BLUE)
    arrow(ax, (11.65, 5.95), (11.65, 5.25), TEAL)
    arrow(ax, (9.55, 4.38), (9.10, 4.38), BLUE)
    arrow(ax, (4.90, 4.38), (4.45, 4.38), AMBER)
    arrow(ax, (2.3, 5.25), (9.60, 5.20), TEAL, curve=-.18)
    ax.text(6.5, 5.45, 'learner observation and outcome feedback',
            ha='center', color=TEAL, fontsize=13, backgroundcolor='white')
    node(ax, .3, 1.05, 4.1, 1.65, '7 / Adaptation hypothesis',
         ['Helpful / neutral / harmful', 'No prescribed human benefit'], AMBER, True)
    node(ax, 4.95, 1.05, 4.1, 1.65, '8 / Assistance-off test',
         ['Retention and task transfer', 'Practice + calibration exposure'], TEAL)
    node(ax, 9.6, 1.05, 4.1, 1.65, 'Essential comparisons',
         ['Neural vs external-only', 'Expert vs learner-only'], TEAL)
    arrow(ax, (2.35, 3.50), (2.35, 2.75), AMBER, dashed=True)
    arrow(ax, (4.45, 1.85), (4.90, 1.85), TEAL)
    ax.text(.35, .38, 'Transfer object: task-relevant information. Retention is a separate biological hypothesis.',
            fontsize=15, color=INK)


def physiological_control(ax):
    node(ax, .3, 6.0, 4.1, 1.65, '1 / Named useful endpoint',
         ['Regulate / trigger / repeat', 'Maintain or delay: extra access'], PURPLE)
    node(ax, 4.95, 6.0, 4.1, 1.65, '2 / Target-specific policy',
         ['Estimate + goal + uncertainty', 'Bounded restoring influence'], BLUE)
    node(ax, 9.6, 6.0, 4.1, 1.65, '3 / Monitored delivery',
         ['Electrical current and charge', 'Contact / timing / compliance'], BLUE)
    arrow(ax, (4.45, 6.8), (4.90, 6.8), PURPLE)
    arrow(ax, (9.10, 6.8), (9.55, 6.8), BLUE)
    node(ax, 9.6, 3.25, 4.1, 1.65, '4 / Accessible pathway',
         ['Uncertain recruitment gain', 'Authority and side-effect limits'], AMBER, True)
    node(ax, 4.95, 3.25, 4.1, 1.65, '5 / Bodily response',
         ['Person-specific dynamics', 'Disturbances / fatigue / delays'], AMBER, True)
    node(ax, .3, 3.25, 4.1, 1.65, '6 / Measured feedback',
         ['External physiological sensor', 'Optional spinal biomarker'], TEAL)
    arrow(ax, (11.65, 5.95), (11.65, 4.95), BLUE)
    arrow(ax, (9.55, 4.08), (9.10, 4.08), AMBER)
    arrow(ax, (4.90, 4.08), (4.45, 4.08), TEAL)
    arrow(ax, (2.35, 4.95), (4.95, 6.35), TEAL, curve=-.14)
    node(ax, .3, .6, 6.2, 1.65, 'Reference: pressure regulation after SCI',
         ['External pressure / lower-thoracic pressor access',
          'No assumed universal ability to lower pressure'], TEAL)
    node(ax, 7.1, .6, 6.6, 1.65, 'Application-specific conclusion',
         ['A triggered event does not establish its postponement',
          'Recording must earn its added information value'], AMBER, True)
    ax.text(.35, 2.65, 'Feedback follows the functional outcome, with freshness and adverse-effect checks.',
            fontsize=15, color=INK)


def setup_fonts():
    # Bundled matplotlib fonts make the build portable; embedded TTF avoids system assumptions.
    font_root = Path(matplotlib.get_data_path()) / 'fonts' / 'ttf'
    pdfmetrics.registerFont(TTFont('SCCI_RH', str(font_root / 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('SCCI_RH-Bold', str(font_root / 'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('SCCI_RH', normal='SCCI_RH', bold='SCCI_RH-Bold',
                                  italic='SCCI_RH', boldItalic='SCCI_RH-Bold')


def build_pdf():
    setup_fonts()
    style = {
        'title': ParagraphStyle('title', fontName='SCCI_RH-Bold', fontSize=32,
                                leading=39, textColor=colors.HexColor(INK), spaceAfter=13),
        'head': ParagraphStyle('head', fontName='SCCI_RH-Bold', fontSize=21,
                               leading=28, textColor=colors.HexColor(INK), spaceAfter=13),
        'sub': ParagraphStyle('sub', fontName='SCCI_RH-Bold', fontSize=12,
                              leading=17, textColor=colors.HexColor(BLUE), spaceBefore=10, spaceAfter=5),
        'body': ParagraphStyle('body', fontName='SCCI_RH', fontSize=10.2,
                               leading=15.4, textColor=colors.HexColor(INK), spaceAfter=10),
        'small': ParagraphStyle('small', fontName='SCCI_RH', fontSize=8.3,
                                leading=12.4, textColor=colors.HexColor(GRAY), spaceAfter=7),
        'cell': ParagraphStyle('cell', fontName='SCCI_RH', fontSize=8.5,
                               leading=12.6, textColor=colors.HexColor(INK)),
    }
    story = []

    def p(text, kind='body'):
        story.append(Paragraph(text, style[kind]))

    def image(name):
        story.append(Image(str(FIG / f'{name}.png'), width=510, height=291.43))
        story.append(Spacer(1, 7))

    def table(headers, rows, widths):
        contents = [[Paragraph(escape(str(t)), style['cell']) for t in headers]]
        contents += [[Paragraph(escape(str(t)), style['cell']) for t in r] for r in rows]
        item = Table(contents, colWidths=widths, repeatRows=1, hAlign='LEFT')
        item.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DDEAF3')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F7FA')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, 0), .7, colors.HexColor('#9AB6CB')),
        ]))
        story.append(item)
        story.append(Spacer(1, 12))

    def page(title, section):
        if story:
            story.append(PageBreak())
        p(section.upper(), 'small')
        p(title, 'head')

    p('PROJECT SCCI RH / STAGE 1 / 8 OCTOBER 2026', 'small')
    p('A spinal interface with<br/>a complete system concept', 'title')
    p('Mechanism and requirements dossier', 'sub')
    p('An entirely digital proposal for invasive spinal recording, computational interpretation, '
      'personalized stimulation and feedback. The two ambitions are retained motor learning '
      'informed by expert recordings and automation of selected physiological responses.')
    image('full-system')
    p('Solid blue blocks are proposed engineering responsibilities; dashed amber blocks contain '
      'task-specific biological access or response assumptions. The drawing establishes a '
      'system boundary, not an implemented implant.', 'small')
    p('<b>Design status:</b> mechanism and requirements for review. Numerical budgets, native '
      'electronics, embedded implementation and implant/companion CAD follow in later stages.')
    p('AstroSam\'s Mind-Link inspires the progression from future vision to inspectable design. '
      'The SCCI application, mechanism, uncertainty analysis and engineering work are SCCI_RH\'s contribution.', 'small')

    page('What the proposed device would do', '01 / Purpose and boundaries')
    p('SCCI_RH would collect target-specific spinal signals, combine them with useful external '
      'measurements, estimate a limited task or bodily state, select a personalized intervention '
      'and monitor the delivered electrical output and functional response.')
    table(['Part', 'Responsibility'], [
        ('SCCI_RH Core / implant', 'Acquire and digitize neural voltages; synchronize and buffer data; '
         'admit bounded commands; schedule and route programmable outputs; monitor current, charge '
         'and compliance; enforce supervision; manage power and telemetry.'),
        ('SCCI_RH Hub / companion', 'Provide task context and external measurements; run session '
         'management and budgeted application services; manage records and operator interaction.'),
        ('SCCI_RH Studio / offline', 'Process expert recordings, learn task representations, analyze '
         'learner calibration, evaluate models and version the resulting policies.'),
        ('Target configuration', 'Supply recording reference/montage and stimulation geometry for '
         'the selected anatomical pathway. Cervical, lumbosacral and thoracic variants differ.'),
    ], [135, 375])
    p('Three kinds of claim', 'sub')
    p('<b>Published component evidence</b> describes what a particular study demonstrated. '
      '<b>Biological hypotheses</b> describe what must become possible for the consumer vision. '
      '<b>Digital verification</b> can establish performance of specified models and engineering '
      'designs within declared envelopes. None substitutes for the others.')
    p('The old v1.0.0 circuit and desktop enclosure remain subsystem references. New electrode '
      'counts, implant geometry and stimulation parameters are not inherited from those artifacts.')
    p('Full-system design is still in progress. This stage reports no new efficacy experiment, '
      'fabricated hardware or tested implantation. Website and video work remain parked.', 'small')

    page('Expert recordings become a personalized training policy', '02 / Motor mechanism')
    image('expert-learning')
    p('The expert contributes a learned, task-related representation of spinal recordings with '
      'context and outcomes. The learner contributes a different body and neural system; a '
      'calibration identifies which available interventions influence the chosen task component.')
    p('The controller receives measured samples and estimated state with uncertainty. It proposes '
      'a bounded electrical intervention during active practice. It receives no hidden true skill '
      'or future trajectory. Literal voltage replay is not a functional inverse.')
    p('<b>Separate learning link:</b> appropriate assistance could improve practice or pairing, '
      'but it could also impair sensory feedback, reduce effort or create dependence. Helpful, '
      'neutral and harmful adaptation must all be allowed. Retention is evaluated after assistance '
      'is removed; online improvement alone is insufficient.')
    p('The starting paper\'s H1 is preserved. Spinal plasticity and rehabilitation provide component '
      'support [4, 5], while healthy expert-to-novice transfer remains unestablished.', 'small')

    page('Make the two information claims testable', '03 / Motor comparisons')
    table(['Policy family', 'External measurements only', 'Neural + external measurements'], [
        ('Learner-only adaptation', 'Personalized learner baseline', 'Tests added neural information'),
        ('Expert-informed adaptation', 'Tests expert task/context information', 'Full proposed SCCI_RH mechanism'),
    ], [138, 186, 186])
    p('The crossed comparison separates expert information from spinal information. It prevents '
      'a favorable expert trajectory or extra calibration exposure from being mistaken for an '
      'advantage of expert neural recordings.')
    table(['Outcome', 'Required interpretation'], [
        ('Assistance-on', 'How much task performance changes while intervention is active.'),
        ('Assistance-off retention', 'What performance remains after a predeclared removal interval.'),
        ('Transfer', 'Whether retained improvement generalizes to an untrained related condition.'),
        ('Acquisition exposure', 'Practice required to meet and retain a predefined criterion; '
         'include calibration cost and trials that never reach the criterion.'),
    ], [138, 372])
    p('Challenge the mechanism', 'sub')
    p('Use held-out learners and contexts, shuffled expert timing, incorrect learner mappings, '
      'ambiguous observations, stimulation artifacts, delay, saturation, dropout and insufficient '
      'authority. Keep an oracle comparison explicitly labelled. A null or harmful result is a '
      'valid and useful result of the digital study.')
    p('A 1.5x or 2x learning gain is an ambition, not a supplied parameter or measured fact. '
      'Motor execution is only part of piano or football expertise; cognitive and perceptual '
      'components remain distributed.', 'small')

    page('Physiological automation follows a named endpoint', '04 / Physiological mechanism')
    image('physiological-control')
    p('A regulator needs a useful measured variable and bounded restoring influence. Triggering '
      'a response needs causal access to the action. Repetition additionally needs recovery and '
      'outcome feedback. Maintaining a state or delaying its termination may require selective '
      'opposing access that triggering evidence does not establish.')
    p('Blood-pressure regulation after SCI is a strong initial reference [6]. Its feedback remains '
      'external pressure measurement, principally systolic pressure in that precedent. A spinal '
      'readout may provide recruitment information, but '
      'its additional value must be tested. A stimulation-plus-external-feedback mode is accurately '
      'described as such within the wider recording/stimulation platform.')
    p('Bladder storage, voiding, cough, respiratory support and selected peripheral sexual '
      'responses require different endpoints and configurations. No universal body-control or '
      'subjective-experience claim follows from this architecture.', 'small')

    page('Choose references without shrinking the future platform', '05 / Task and access choices')
    table(['Candidate', 'Useful starting point', 'Unresolved leap'], [
        ('Lower-limb coordination', 'Locomotor recruitment and timing studies; footwork motivates '
         'a consumer coordination task.', 'Healthy retained expert skill transfer; neural value '
         'beyond motion/EMG; dynamic balance.'),
        ('Cervical / piano coordination', 'Upper-limb stimulation studies support access to '
         'movement-related circuits.', 'Independent finger readout/control, task representation '
         'and useful retention without sensory interference.'),
        ('Pressure regulation', 'Human lower-thoracic stimulation with pressure feedback gives '
         'a defined pathway and controlled variable.', 'Healthy use, optional neural recording '
         'value, bounded pressor authority and side effects.'),
    ], [117, 197, 196])
    p('Provisional recommendation: lower-limb coordination and pressure regulation as the first '
      'quantitative reference configurations. Keep the cervical/piano and other physiological '
      'variants in the capability map. These are reference cases for platform engineering, not '
      'evidence of consumer efficacy.')
    table(['Access candidate', 'Tradeoff to resolve'], [
        ('Shared epidural recording/stimulation', 'Simpler shared access; evoked responses are '
         'distinct from decoding spontaneous expert activity.'),
        ('Intradural surface recording + epidural stimulation', 'Comparison baseline with '
         'separate signal/recruitment access; artifacts, chronic stability and human integration remain unresolved.'),
        ('Penetrating recording with selected stimulation access', 'Potential local access; '
         'sampling bias, tissue response, durability and mechanical burden increase.'),
    ], [200, 310])
    p('Surface and intraspinal recording studies [1, 2] motivate alternatives, not a selected '
      'chronic human decoder. Counts and placements follow signal/control requirements. Spinal '
      'segment, root, vertebral level and actual electrode position remain distinct coordinates.', 'small')

    page('Engineering budgets must close before detailed CAD', '06 / Requirements and interfaces')
    p('The detailed dossier contains 36 requirements, 14 explicit assumptions and 14 capability '
      'entries. The tables define responsibilities and staged checks. This brief summarizes the '
      'quantities that Stage 2 must make numerical.')
    table(['Budget', 'Quantities and constraints'], [
        ('Acquisition', 'Signal and electrode offset ranges; input noise; bandwidth; ADC resolution; '
         'montage; artifact saturation and recovery.'),
        ('Data and compute', 'Sampled channels x sample rate x bits, framing, timestamps, buffers, '
         'estimation cost and memory; contact count is a separate quantity.'),
        ('Timing', 'Filtering + conversion + recovery + computation + transport + scheduling; '
         'freshness, jitter and clock error in each operating mode.'),
        ('Stimulation', 'Routing and independent sources; load/polarization voltage plus driver '
         'headroom; actual integrated current per phase; charge and duty-cycle limits.'),
        ('Power and heat', 'Acquisition, compute, telemetry, monitoring, storage/transfer and '
         'stimulation energy; realistic modes, efficiency and thermal uncertainty.'),
        ('Mechanical interfaces', 'Target geometry; conductors and feedthroughs; populated board, '
         'energy-storage, cable and connector envelopes; stiffness and fit assumptions.'),
    ], [118, 392])
    p('Fault behavior is application-specific', 'sub')
    p('Radio loss, stale measurements, brownout, reset and interrupted phases need independent '
      'handling. Disable new output admission on invalid state; track delivered charge and '
      'remaining power. An interrupted pulse does not justify an automatic opposite pulse. '
      'Removing assistance can also carry physiological risk, so fallback behavior requires '
      'target-specific review.')
    p('Operating modes include initialization, self-test, recording, expert collection, learner '
      'calibration, assisted practice, unassisted assessment, physiological regulation, charging '
      'and fault recovery. Concurrent applications need explicit resource arbitration.', 'small')

    page('What verification can establish', '07 / Validation and next stage')
    table(['Work package', 'Completion evidence', 'Remaining boundary'], [
        ('Stage 1 / specification', 'Coherent mechanism chains, responsibilities, source '
         'audit, requirements, assumptions, links and reviewed figures.', 'A proposal has not been built.'),
        ('Stage 2 / numerical architecture', 'Closed signal, timing, output, energy and '
         'mechanical envelopes with uncertainty.', 'Budgets depend on declared load and access models.'),
        ('Stage 3 / computational mechanism', 'Observable-only model, fair comparisons, '
         'held-out calibration and negative results.', 'Model adaptation is not human learning.'),
        ('Stages 4-5 / electronics and CAD', 'Native designs, monitored waveform models, '
         'fault tests, matching pinouts and interference/export checks.', 'No fabricated hardware or '
         'implantation validation.'),
        ('Stage 6 / integrated research release', 'End-to-end digital trace, reproducibility, '
         'source-linked manuscript and repository review.', 'Biological efficacy, chronic stability '
         'and clinical use need separate future evidence.'),
    ], [145, 205, 160])
    p('Recommended next decision', 'sub')
    p('Review the motor reference and physiological endpoint before fixing target anatomy. '
      'Then calculate channel scaling, waveform/load and timing budgets; compare access options '
      'against those requirements. If information or control authority is insufficient, revise '
      'the capability or configuration before board routing and implant geometry.')
    p('Full source and design records', 'sub')
    p('docs/stage1/README.md is the entry point. The source audit records study-specific support '
      'and limits; the requirements and verification matrix map future checks. The Stage 1 '
      'verification receipt records only checks actually performed. The original 28-page '
      'source is preserved read-only with its stated 30 September 2026 cutoff.', 'small')

    page('Selected primary foundations', '08 / Source guide')
    refs = [
        ('1', 'El Hadwe et al. (2026). Surface circumferential spinal cord recording in freely moving rodents. Nature Communications.',
         'https://doi.org/10.1038/s41467-026-75128-z', 'Spinal surface observations in animal studies; '
         'not a chronic human expert decoder.'),
        ('2', 'Fan et al. (2023). A Hyperflexible Electrode Array for Long-Term Recording and Decoding of Intraspinal Neuronal Activity. '
         'Advanced Science.', 'https://doi.org/10.1002/advs.202303377', 'Alternative recording access '
         'and mouse decoding; human integration remains separate.'),
        ('3', 'Formento et al. (2018). Electrical spinal cord stimulation must preserve proprioception '
         'to enable locomotion in humans with spinal cord injury. Nature Neuroscience.',
         'https://doi.org/10.1038/s41593-018-0262-6', 'Sensory interference matters when choosing timing '
         'and recruitment.'),
        ('4', 'Nishimura et al. (2013). Spike-timing-dependent plasticity in primate corticospinal '
         'connections induced during free behavior. Neuron.',
         'https://doi.org/10.1016/j.neuron.2013.08.028', 'Hybrid cortical-triggered spinal plasticity; '
         'not spinal-only expert transfer.'),
        ('5', 'McPherson et al. (2015). Targeted, activity-dependent spinal stimulation produces '
         'long-lasting motor recovery in chronic cervical spinal cord injury. PNAS.',
         'https://doi.org/10.1073/pnas.1505383112', 'Activity-linked rehabilitation in injured rats; '
         'not a healthy learning-speed multiplier.'),
        ('6', 'Phillips et al. (2025). An implantable system to restore hemodynamic stability after '
         'spinal cord injury. Nature Medicine.',
         'https://doi.org/10.1038/s41591-025-03614-w', 'Human target-specific pressure feedback and '
         'lower-thoracic stimulation; external pressure measurement.'),
        ('7', 'de Freitas et al. (2026). Spinal cord stimulation for upper limb motor function in people with chronic post-stroke hemiparesis: a feasibility trial. '
         'Nature Medicine.', 'https://doi.org/10.1038/s41591-026-04435-1', 'Upper-limb access '
         'component evidence; not independent healthy piano expertise transfer.'),
    ]
    for number, title, url, boundary in refs:
        p(f'<b>[{number}] {escape(title)}</b><br/><link href="{url}" color="{BLUE}">'
          f'{escape(url)}</link><br/>{escape(boundary)}', 'small')
    p('Evidence handling', 'sub')
    p('This is a narrative design audit, not a systematic review. Study counts, access scope '
      'and important extrapolation limits are in docs/stage1/source-audit.csv. Use those '
      'records for study endpoints, access scope and unverified details.', 'small')
    p('Control foundations: Astrom and Murray, <i>Feedback Systems</i>, author-hosted book. '
      '<link href="https://www.cds.caltech.edu/~murray/books/AM08/pdf/am08-complete_06Oct09.pdf" '
      f'color="{BLUE}">Author-hosted text</link>. Observability and bounded control authority '
      'constrain the interface even if computation becomes ideal.', 'small')
    p('Inspiration: <link href="https://github.com/sam-astro/Mind-link" '
      f'color="{BLUE}">AstroSam / Mind-Link repository</link> and the video identified in the '
      'project introduction. Engineering presentation inspiration is distinct from SCCI evidence.', 'small')

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#D5E0E9'))
        canvas.line(42, 42, 552, 42)
        canvas.setFont('SCCI_RH', 8)
        canvas.setFillColor(colors.HexColor(GRAY))
        canvas.drawString(42, 27, 'PROJECT SCCI RH  |  STAGE 1 PROPOSAL  |  8 OCT 2026')
        canvas.drawRightString(552, 27, f'{doc.page} / 9')
        canvas.restoreState()

    doc = SimpleDocTemplate(str(OUT), pagesize=(594, 842), leftMargin=42,
                            rightMargin=42, topMargin=40, bottomMargin=58,
                            title='Project SCCI RH - Stage 1 Mechanism and Requirements',
                            author='Project SCCI RH', subject='Full proposed SCCI design specification')
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    figure('full-system', full_system)
    figure('expert-learning', expert_learning)
    figure('physiological-control', physiological_control)
    build_pdf()
    print(f'Built {OUT.name} and three SVG/PNG mechanism figures.')


if __name__ == '__main__':
    main()
