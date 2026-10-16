const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

test("item-code choices preserve values while escaping dropdown HTML", () => {
    const handlers = {};
    const frappe = {
        ui: { form: { on: (doctype, events) => { handlers[doctype] = events; } } },
        utils: { escape_html: value => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;") }
    };
    const source = fs.readFileSync(path.join(__dirname, "../reli_lims/reli_lims/doctype/test_program/test_program.js"), "utf8");
    vm.runInNewContext(source, { frappe });
    let choices;
    const frm = {
        doc: { items: [{ item_code: "LT" }, { item_code: "<img src=x onerror=alert(1)>" }] },
        fields_dict: { sample_assignments: { grid: {
            update_docfield_property: (_field, _property, options) => { choices = options; }
        } } }
    };
    handlers["Test Program"].update_item_choices(frm);
    choices = choices.map(choice => typeof choice === "string" ? { value: choice, label: choice } : choice);
    assert.equal(choices[0].value, "LT");
    assert.equal(choices[1].value, "<img src=x onerror=alert(1)>");
    assert.equal(choices[1].label, "&lt;img src=x onerror=alert(1)&gt;");
});

function removalHandlers(rows = {}) {
    const handlers = {};
    const frappe = {
        ui: { form: { on: (doctype, events) => { handlers[doctype] = events; } } },
        get_doc: (_doctype, name) => rows[name],
        throw: message => { throw new Error(message); },
        utils: { escape_html: value => value }
    };
    const source = fs.readFileSync(path.join(__dirname, "../reli_lims/reli_lims/doctype/test_program/test_program.js"), "utf8");
    const translate = (message, args = []) => message.replace(/\{(\d+)\}/g, (_match, index) => args[index]);
    vm.runInNewContext(source, { frappe, __: translate });
    return handlers;
}

test("assigned item cannot be removed without first clearing its assignments", () => {
    const events = removalHandlers({ row1: { item_code: "LT", status: "Pending" } })["Test Program Item"];
    const frm = { doc: { sample_assignments: [{ item_code: "LT", sample: "SMP-1" }] } };
    assert.throws(() => events?.before_items_remove?.(frm, "Test Program Item", "row1"), /LT.*assignment/i);
});

test("assigned sample removal explains the association to clear", () => {
    const events = removalHandlers({ row1: { sample: "SMP-1" } })["Test Program Sample"];
    const frm = { doc: { sample_assignments: [{ item_code: "LT", sample: "SMP-1" }] } };
    assert.throws(() => events?.before_samples_remove?.(frm, "Test Program Sample", "row1"), /SMP-1.*assignment/i);
});

test("started items cannot be removed even after clearing assignments", () => {
    const events = removalHandlers({ row1: { item_code: "LT", status: "Running" } })["Test Program Item"];
    assert.throws(() => events?.before_items_remove?.({ doc: { sample_assignments: [] } }, "Test Program Item", "row1"), /started/i);
});

test("unassigned pending items and samples may be removed", () => {
    const events = removalHandlers({ item: { item_code: "LT", status: "Pending" }, sample: { sample: "SMP-1" } });
    const frm = { doc: { sample_assignments: [] } };
    assert.doesNotThrow(() => events["Test Program Item"]?.before_items_remove?.(frm, "Test Program Item", "item"));
    assert.doesNotThrow(() => events["Test Program Sample"]?.before_samples_remove?.(frm, "Test Program Sample", "sample"));
});

test("blank grid rows can be removed without matching blank assignments", () => {
    const events = removalHandlers({ item: { status: "Pending" }, sample: {} });
    const frm = { doc: { sample_assignments: [{}] } };
    assert.doesNotThrow(() => events["Test Program Item"].before_items_remove(frm, "Test Program Item", "item"));
    assert.doesNotThrow(() => events["Test Program Sample"].before_samples_remove(frm, "Test Program Sample", "sample"));
});
