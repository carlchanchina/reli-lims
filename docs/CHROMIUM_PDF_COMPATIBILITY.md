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

Runtime compatibility was verified on 2026-11-01 against Frappe 16.52.0 /
ERPNext 16.51.1 and Chrome for Testing 133.0.6943.35, after installing the
minimal shared-library dependencies and Noto CJK fonts. The existing templates
were loaded from an isolated candidate directory on the production host; this
was not a deployment of the application or a real business-document acceptance.
Database sessions were read-only, documents remained unsaved, and no File
records were created. Business-record fingerprints and Portal flags matched
before and after the test.

Actual outputs from 100-row, clearly labelled non-business fixtures:

| Path | Bytes | Pages |
| --- | ---: | ---: |
| Reli Quotation template | 175789 | 6 |
| Reli Test Request template | 184113 | 4 |
| Reli Test Report template | 185025 | 6 |
| Native Quotation Classic | 220571 | 9 |

All outputs report Skia/PDF m133. Chinese glyphs, table continuation and
existing signature/terms sections were visually checked. Existing templates
were not redesigned: titles remain on the first page, signatures remain at
the end, and native Quotation Classic retains its configured hidden page
numbers. A separate two-page native Chromium fixture confirmed repeated
Chinese headers/footers and page numbers 1/2 and 2/2.

Chromium embeds Noto CJK subsets as Type3 fonts; its ToUnicode text may contain
Unicode compatibility radicals. Text assertions use NFKC normalization. This
is a text-extraction caveat, not a visual missing-glyph result.

PDF SHA256 values:

- Reli Quotation: `1b9b5b05adb21ba974dd5b1cbe4112451cbea1d323bbcb606ee5105ccd846550`
- Reli Test Request: `4559019588d7ad5dd3857d05218b9ada9303846cf2f4d4d786c684943c944c9f`
- Reli Test Report: `712153d6fcf3afa7e3e6f9e274375db46f68b5b9ef1442f9dee158db0406eab3`
- Native Quotation Classic: `9156ebf261d842929bf51eb4cf4a4c591c3a8f39f9ac6222340a4a393f5206aa`

These PDFs are compatibility fixtures, not real quotations, test results or
issued/stamped reports. Merge/deployment and overall release acceptance are
separate steps.
No schema migration or new Portal feature flag is required for this renderer
change. Restoring the previous application version rolls back the call, but
would also restore the previous engine dependency; it is not evidence of PDF
readiness.

## Tests

Run `python -m unittest discover -s tests -p test_document_output.py -v`.
The suite covers native Chromium selection, HTML escaping, failure propagation
without a legacy fallback, attachment permission boundaries, and existing
DOCX/XLSX output contracts.
