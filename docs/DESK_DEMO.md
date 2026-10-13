# Reli LIMS Desk demo

Use the `wekona-test.localhost` test site on the existing ERPNext server.
Assign Lab Manager, Lab Engineer and Lab Reviewer as appropriate. ERPNext roles
must separately permit the user to read/select the Project, Customer and Asset.
Administrator can run the whole demo; normal users should use the assigned roles.

1. In ERPNext, select the existing testing Project and laboratory Asset.
2. Open Testing Center → Samples. Register two samples against that Project,
   with received date and positive quantity. Customer derives from Project.
3. As Lab Manager, create three Active Test Standards (A, B, C) and three Test
   Methods (Low Temperature, High Temperature, Vibration). A method's default
   standard is optional; the execution item independently chooses its standard.
4. Create a Test Program against the same Project. Add both Samples to Samples.
5. Add three Items with stable codes `LT`, `HT`, `VIB`, corresponding methods,
   one standard each, an engineer, and the ERPNext Asset. Add test conditions.
6. In Sample Assignments, add one row per applicable item/sample pair. Select
   item codes from the suggestions. Every item needs at least one program sample;
   an item can apply to both samples. Existing item codes cannot be renamed.
7. Save, then move items through `Pending → Ready → Running → Completed`.
   Save after each transition. Running records actual start. Completed requires
   both result and conclusion, and records actual end. Attach optional raw files
   on each item. Running execution basis and sample assignments are locked.
8. As Lab Reviewer or Lab Manager, move Completed items to Reviewed and save.
   Reviewed item content is locked. Program progress is derived from item states;
   Completed means execution finished, while item status distinguishes review.
9. Create Test Report linked to that Program and the same Project. Fill the
   overall conclusion and assign reviewer. Save each status transition:
   `Draft → Engineering Complete → Review → Approved → Issued`.
10. Lab Manager approves and issues. Upload the final PDF as a private attachment
    on the Test Report before issue. Approval records the acting manager. Approved
    business data is frozen; only a manager may replace the PDF before issue.
11. Issue records issued date. Issued/Revised reports cannot be edited or deleted;
    their program is frozen. A manager can mark an old report Revised without
    changing its content; create a separate new report document/version for the
    replacement deliverable.

Cancellation is manager-only. Cancel without changing program content; cancelled
programs cannot be reopened. Draft program associations can be corrected, but
removing a sample/item also requires removing its Sample Assignment rows.

The app does not automatically generate report PDFs or create Quality Inspection.
Existing Quality Inspection can be optionally linked per item. Attachments use
Frappe File. Analytical reports, dashboard metrics and portal APIs are deferred.

## Automated verification

Run all app tests on the designated test site, never on a live operational site:

```sh
bench --site wekona-test.localhost run-tests --app reli_lims
```

For this Pilot-managed deployment without a bench executable, from its `sites`
directory invoke the equivalent dispatcher with the bench environment Python:

```sh
/home/frappe/pilot/benches/dev-bench/env/bin/python -m frappe.utils.bench_helper frappe --site wekona-test.localhost run-tests --app reli_lims
```

The acceptance test creates real ERPNext Project, Company and Asset records,
then two Samples, three methods/standards, one Program and a private PDF report.
Business test records are rolled back by Frappe's test runner.
