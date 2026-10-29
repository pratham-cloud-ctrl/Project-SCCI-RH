# Actual independent inspector revisions

The `09027f...` SHA256-named source identifies the original independent inspector
that successfully produced the future and harness native receipts. The Project
SCCI RH migration renamed project identifiers in the archived copies and phase
metadata while preserving geometry and numerical results. Original executed
bytes remain available in the immutable Git baseline. Current receipts bind the
exact renamed content, and the verifier resolves retained historical filenames
by their current content digest. This migration does not claim a new execution
of those historical inspections.

The current inspector corrects the reference enclosure's overall envelope to
include its four feet (panels occupy Z=8..240 mm; the assembled envelope includes
feet down to Z=0 mm). It also writes local, machine-generated successful phase
checkpoints for interruption recovery. The reference audit is rerun with this
corrected source. No CAD geometry or acceptance clearance is changed, and no
pass is reconstructed from an incomplete execution log.

The `2bf920...` source identifies the corrected inspector that completed the four
reference source/native/export phases recorded in `../stage5-reference-phases/`.
Those records carry the same explicit naming migration described above; their
original bytes remain in Git. Its later whole-compound distance operation did
not finish and produced no complete pass receipt. The final reference receipt
identifies `scripts/inspect_stage5_reference.py`, which explicitly binds those
completed phases and the separately completed exact solid-pair distance run,
then performs fresh saved-native validity, topology, nearest-pair witness and
material-interference checks. Each receipt retains the identity of its original
executed source and the exact current migrated representation.
