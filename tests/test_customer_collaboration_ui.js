const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function form(state) {
    const registrations = [];
    const buttons = new Map();
    const calls = [];
    let dialog;
    const frappe = {
        user_roles: ['Lab Manager'],
        ui: {form: {on: (...args) => registrations.push(args)}, Dialog: class {
            constructor(options) { this.options = options; dialog = this; }
            show() {}
            hide() {}
            get_value() { return 'Review note'; }
        }},
        call: (method, args) => { calls.push({method, args}); return Promise.resolve({message: []}); },
        msgprint() {},
    };
    vm.runInNewContext(fs.readFileSync('reli_lims/reli_lims/doctype/test_request/test_request.js', 'utf8'), {
        frappe, __: text => text,
    });
    const handlers = registrations.find(([dt]) => dt === 'Test Request')[1];
    const frm = {
        doc: {doctype: 'Test Request', name: 'REQ-P4', docstatus: 0, customer_confirmation_state: state},
        is_new: () => false, is_dirty: () => false, reload_doc: () => Promise.resolve(),
        add_custom_button(label, callback) { buttons.set(label, callback); return {addClass() {}}; },
        call(method, args) {
            // Native frm.call string overload attaches the current document.
            calls.push({method, args, doc: typeof method === 'string' ? this.doc : method.doc});
            return Promise.resolve({message: {url: '/customer-request/REQ-P4', expires_on: '2026-12-01'}});
        },
    };
    handlers.customer_collaboration(frm);
    return {frm, buttons, calls, dialog: () => dialog};
}

test('Desk lab review invokes a document method with the bound request', async () => {
    const setup = form('Awaiting Lab Review');
    setup.buttons.get('实验室审核')();
    setup.dialog().options.primary_action({note: 'P4 review'});
    await Promise.resolve();
    assert.equal(setup.calls[0].method, 'review_customer_fill');
    assert.equal(setup.calls[0].doc.name, 'REQ-P4');
    assert.equal(setup.calls[0].args.approve, 1);
});

test('Desk customer link generation is bound to the request and link lookup uses its service API', async () => {
    const setup = form('Draft');
    setup.buttons.get('发送客户填写链接')();
    setup.dialog().options.primary_action({expires_days: 7});
    await Promise.resolve();
    assert.equal(setup.calls[0].method, 'send_customer_fill_link');
    assert.equal(setup.calls[0].doc.name, 'REQ-P4');
    setup.buttons.get('查看客户链接')();
    await Promise.resolve();
    assert.equal(setup.calls[1].method, 'reli_lims.customer_share.list_links');
    assert.equal(setup.calls[1].args.name, 'REQ-P4');
});
