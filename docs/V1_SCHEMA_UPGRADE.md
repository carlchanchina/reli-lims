# V1 native schema upgrade and display configuration

No additional business DocType is introduced. The native Test Request JSON owns
the Quotation/Sales Order links. The existing confirmation setup owns the eleven
confirmation/collaboration fields and File customer visibility flag.

`reli_lims.request_confirmation_setup.after_migrate` remains the repeatable entry
point. It now checks existing storage types before upserts and runs a read-only
readiness gate afterward. Missing native links, incompatible field properties,
unresolvable File handlers or missing native Lab Manager submit permission fail
the deployment rather than silently succeeding. No business backfill, status
activation, confirmation fabrication, permission broadening or commit is added.

## Apply and verify

Use the normal site-specific Frappe migrate process with the approved candidate.
Native DocType sync must run before `after_migrate`; calling only the custom
field helper is not a substitute for syncing the native commercial links.

After migration, execute the read-only
`reli_lims.request_confirmation_setup.verify_schema` gate. Expected result:
eleven confirmation fields, two native commercial links, one File visibility
flag, four resolvable File handlers, and Lab Manager submit permission. Existing
native submit and attachment authorization logic are retained.

For Bridge, explicitly run its existing Portal runtime/party schema helpers;
ordinary Bridge after_migrate is not a replacement for those helpers.

## Upgrade, replay and rollback evidence

On 2026-11-01, an original-host private-socket database restored from the frozen
pre-upgrade backup was migrated with the full native pipeline twice. Both
readiness gates passed. The eleven monitored business tables retained their
counts and name/modified fingerprints; the standard remained Draft. No worker
or scheduler ran. Production databases were not upgraded in this test.

The upgraded isolated database was then restored from the original backup.
Counts and name/modified fingerprints matched the baseline, and the expanded
schema was absent. This validates snapshot rollback, not transactional DDL
rollback. Restore the matched DB, Files, config and code in a controlled window;
do not drop the new columns or delete confirmation history in a live database.
Keep intake/submission unavailable while rolling back to older code.

## Standard display only

The existing `full_name` title field is shown in Links; standard code, title,
version and full name are searchable. The list exposes title and version along
with code. Native Property Setters can apply these same JSON-declared display
properties to an existing installation before its full application upgrade.
Preserve a Property Setter snapshot for reversal. Do not change standard IDs,
linked IDs, content, approval state or the existing stored full-name string.

A Draft standard remains Draft. Existing native Active Standard requirements
still govern formal requests. Library-wide cleanup is not a prerequisite for
public pages, registration, inquiry or quotation operations.

## Tests

`python -m unittest discover -s tests -p 'test_request*.py'` passes 19 tests.
`python -m unittest discover -s tests -p test_standard_display.py` passes one test.
Seven of these cover migration/replay, pre-upsert storage conflicts, missing
native links, File read-only enforcement, hook resolution, Lab Manager
permission and optional additions for legacy drafts.

## Formal submission: active execution masters only

The previous scope validator required a nonempty Method/Standard reference but
did not check the referenced state. Native submission now checks that each
Method is active and each Standard is Active before existing Project creation.
References are deduplicated and locked in a consistent order. Draft editing,
inquiry and quotation paths are not restricted by this additional guard.

Six tests cover inactive/missing masters, Draft/Superseded standards, locked
reads, repeated items, and invocation from the existing submission guard. The
request suite now passes 25 tests. An original-host disposable database also
verified that the original Draft standard is rejected, an explicitly labelled
non-business Active fixture is accepted, and an inactive Method is rejected;
all fixture changes were rolled back. No production standard was activated.
