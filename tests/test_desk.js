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
