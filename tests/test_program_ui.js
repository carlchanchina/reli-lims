const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function setup() {
    const handlers = {};
    const context = {frappe: {ui: {form: {on(dt, events) {handlers[dt] = {...handlers[dt], ...events};}}},
        utils: {escape_html: value => value}, get_doc: () => ({item_code: 'T1', status: 'Pending'}),
        throw(message) {throw new Error(message);}}, __: value => value};
    vm.runInNewContext(fs.readFileSync('reli_lims/reli_lims/doctype/test_program/test_program.js','utf8'), context);
    const frm = {doc: {sample_assignments: [{item_code:'T1',sample:'S1'}, {item_code:'T2',sample:'S2'}]},
        clear_table(field) {this.doc[field] = [];}, add_child(field,row) {this.doc[field].push(row);},
        refresh_field() {}, events: {update_item_choices() {}}};
    return {handlers, frm};
}
test('removing an unstarted test cleans its hidden sample relation and preserves others', () => {
    const {handlers,frm} = setup();
    handlers['Test Program Item'].before_items_remove(frm,'Test Program Item','row1');
    assert.equal(frm.doc.sample_assignments.length,1);
    assert.equal(frm.doc.sample_assignments[0].item_code,'T2');
});
