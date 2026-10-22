const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
test('a late program lookup cannot overwrite a newer report selection', async () => {
    let events;
    const pending = {};
    const context = {frappe:{ui:{form:{on(dt, handlers) {events=handlers;}}},
        db:{get_value(dt,name) {return new Promise(resolve => {pending[name]=resolve;});}}}};
    vm.runInNewContext(fs.readFileSync('reli_lims/reli_lims/doctype/test_report/test_report.js','utf8'),context);
    const frm={doc:{test_program:'A'}, is_new:()=>true, async set_value(values) {Object.assign(this.doc,values);}};
    const first=events.test_program(frm);
    frm.doc.test_program='B';
    const second=events.test_program(frm);
    pending.B({message:{project:'B-project'}}); await second;
    pending.A({message:{project:'A-project'}}); await first;
    assert.equal(frm.doc.project,'B-project');
});
