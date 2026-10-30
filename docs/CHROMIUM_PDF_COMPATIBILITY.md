# Frappe v16 Chromium PDF compatibility

Reli Document Output PDF rendering uses Frappe's native
`frappe.utils.pdf.get_chrome_pdf`, explicitly selecting `chrome`. The file-based
HTML templates and existing PDF/DOCX/XLSX service interfaces are retained.
DOCX/XLSX renderers and business DocTypes are unchanged.

This corrects the former direct `get_pdf` call, which uses the legacy pdfkit
pipeline even when Print Settings selects Chrome. There is no legacy fallback:
a Chromium failure propagates without creating an output attachment.

## Compatibility and deployment

The native call signature and A4/margin option conversion have been checked
against Frappe 16.52.0. Chromium discovery, process lifecycle, rendering and PDF
transformation remain owned by Frappe. Reli does not launch another PDF engine
or install a browser.

Before deployment, verify that the target Frappe provides `get_chrome_pdf` and
that its configured/discovered Chromium executable starts with all shared
libraries present. Run the existing templates with clearly labelled non-business
fixtures; check Chinese text, multi-page tables, headers/footers and output
hashes. Unit tests do not replace this runtime and visual acceptance.

Production acceptance is pending: the existing Chromium executable currently
cannot start because required shared libraries are missing. No successful
production PDF or visual compatibility result is claimed by this change.
No schema migration or new Portal feature flag is required for this renderer
change. Restoring the previous application version rolls back the call, but
would also restore the previous engine dependency; it is not evidence of PDF
readiness.

## Tests

Run `python -m unittest discover -s tests -p test_document_output.py -v`.
The suite covers native Chromium selection, HTML escaping, failure propagation
without a legacy fallback, attachment permission boundaries, and existing
DOCX/XLSX output contracts.
