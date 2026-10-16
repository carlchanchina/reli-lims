const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function handlers() {
  const events = {};
  vm.runInNewContext(fs.readFileSync('reli_lims/reli_lims/doctype/test_request/test_request.js','utf8'), {
    frappe: {ui:{form:{on:(name,value)=>events[name]=value}},
      user_roles:['Lab Manager'],utils:{escape_html:s=>s.replaceAll('<','&lt;')}},
    __:s=>s
  });
  return events;
}
test('draft request never offers receipt or program creation',()=>{
  const buttons=[];
  const frm={doc:{docstatus:0,samples:[],items:[]},is_new:()=>false,
    add_custom_button:label=>buttons.push(label),events:handlers()['Test Request'],
    fields_dict:{photos:{grid:{update_docfield_property(){}}},sample_assignments:{grid:{update_docfield_property(){}}}}};
  frm.events.refresh(frm);
  assert.equal(buttons.length,0);
});
test('confirmed request exposes receipt and generation actions',()=>{
  const events=handlers()['Test Request'];const buttons=[];
  const frm={doc:{docstatus:1,project:'P1',samples:[],items:[]},is_new:()=>false,
    add_custom_button:label=>buttons.push(label),events,
    fields_dict:{photos:{grid:{update_docfield_property(){}}},sample_assignments:{grid:{update_docfield_property(){}}}}};
  events.refresh(frm);
  assert.ok(buttons.includes('Receive Samples'));
  assert.ok(buttons.includes('Create Test Program'));
});
test('receipt dialog loads outstanding samples rather than resetting received ones',()=>{
  const events={};let request;let opened;
  vm.runInNewContext(fs.readFileSync('reli_lims/reli_lims/doctype/test_request/test_request.js','utf8'),{
    frappe:{ui:{form:{on:(name,value)=>events[name]=value}},call:options=>request=options},__:s=>s});
  const frm={doc:{name:'REQ-1'},events:{open_receipts:(_frm,rows)=>opened=rows}};
  events['Test Request'].receive_samples(frm);
  assert.equal(request.method,'reli_lims.services.test_request.get_receivable_samples');
  request.callback({message:[{sample_code:'S2',quantity:1}]});
  assert.equal(opened.length,1);
  assert.equal(opened[0].sample_code,'S2');
});
