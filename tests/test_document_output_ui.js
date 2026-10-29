const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('three native forms share one saved-source dialog with default PDF and safe retry', async () => {
    const handlers = {}, calls = [], messages = [];
    let dialog, button, fail = false;
    const frappe = {ui: {form: {on(dt, events) {handlers[dt] = events;}}, Dialog: class {
        constructor(config) {this.config=config; dialog=this;}
        show() {} hide() {this.hidden=true;} disable_primary_action() {this.disabled=true;}
        enable_primary_action() {this.disabled=false;}
    }}, call: async options => {
        calls.push(options);
        if (options.method.endsWith('get_templates')) return {message:[{name:'commission',label:'检测委托单',formats:['pdf','docx','xlsx'],default_format:'pdf'}]};
        if (fail) throw Error('renderer unavailable');
        return {message:{file_url:'/private/files/example.pdf',file_name:'示例.pdf'}};
    }, msgprint(message) {messages.push(message);}, utils: {escape_html:v=>v}};
    const context = {frappe, __:v=>v};
    const script=fs.readFileSync('reli_lims/public/js/document_output.js','utf8');
    vm.runInNewContext(script,context);
    vm.runInNewContext(script,context); // hooks loaded again for another form
    assert.equal(Object.keys(handlers).length,3);
    for (const dt of ['Quotation','Test Request','Test Report']) {
        let dirty=false;
        const frm={doc:{name:'SOURCE-1'},perm:[{read:1,print:1}],is_new:()=>false,is_dirty:()=>dirty,
            add_custom_button(label,cb) {assert.equal(label,'生成文档');button=cb;},reload_doc() {}};
        handlers[dt].refresh(frm);
        dirty=true; const before=calls.length; await button(); assert.equal(calls.length,before);
        dirty=false; await button();
        assert.equal(dialog.config.fields[1].default,'pdf');
        dirty=true; await dialog.config.primary_action({template:'commission',output_format:'pdf'});
        assert.equal(calls.at(-1).method.endsWith('get_templates'),true);
        dirty=false; fail=true;
        await assert.rejects(dialog.config.primary_action({template:'commission',output_format:'pdf'}));
        assert.equal(dialog.disabled,false);
        fail=false;
        await dialog.config.primary_action({template:'commission',output_format:'pdf'});
        assert.equal(calls.at(-1).args.name,'SOURCE-1');
        assert.equal(calls.at(-1).args.doctype,dt);
        assert.ok(dialog.hidden);
    }
});
