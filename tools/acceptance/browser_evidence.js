#!/usr/bin/env node
/**
 * 浏览器证据采集：真实登录后截图 + 生成正式打印 PDF。
 *
 * 该 bench 的 wkhtmltopdf 是 unpatched qt，服务端直出 PDF 不可靠，因此 PDF 由
 * 无头 Chrome 从真实 printview 页面打印，产物可直接作为交付证据。
 *
 * 用法：
 *   node tools/acceptance/browser_evidence.js --base http://carl:8000 \
 *        --user demo-lab-manager@example.com --password '***' \
 *        --out /tmp/evidence --job /tmp/job.json
 *
 * job.json 结构：
 *   {
 *     "shots": [{"name": "01-home", "path": "/app", "mobile": false, "wait": 1500}],
 *     "pdfs":  [{"name": "report", "doctype": "Test Report", "docname": "RPT-00001"}]
 *   }
 * 链接类页面（客户免登录）直接给出完整 path，脚本不做任何打印，避免日志泄露密钥。
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

function parseArgs() {
  const args = {};
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i].startsWith('--')) {
      args[argv[i].slice(2)] = argv[i + 1];
      i += 1;
    }
  }
  return args;
}

async function main() {
  const args = parseArgs();
  const base = args.base || 'http://carl:8000';
  const out = args.out || '/tmp/evidence';
  const job = JSON.parse(fs.readFileSync(args.job, 'utf8'));
  fs.mkdirSync(out, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: [
      '--host-resolver-rules=MAP carl 192.168.10.204',
      '--no-sandbox',
      '--disable-dev-shm-usage',
    ],
  });

  const context = await browser.createBrowserContext();
  const page = await context.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  if (args.user) {
    const response = await page.goto(`${base}/login`, { waitUntil: 'networkidle2' });
    if (!response || response.status() >= 400) throw new Error('登录页不可用');
    const loggedIn = await page.evaluate(async (usr, pwd) => {
      const res = await fetch('/api/method/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ usr, pwd }).toString(),
        credentials: 'same-origin',
      });
      const payload = await res.json();
      return { ok: res.ok, message: payload.message || payload.exc_type || '' };
    }, args.user, args.password);
    if (!loggedIn.ok) throw new Error(`登录失败：${loggedIn.message}`);
    console.log(`登录成功：${args.user}（${loggedIn.message}）`);
  }

  const results = { shots: [], pdfs: [] };

  for (const shot of job.shots || []) {
    if (shot.mobile) {
      await page.setViewport({ width: 414, height: 896, deviceScaleFactor: 3, isMobile: true });
    } else {
      await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });
    }
    const url = shot.path.startsWith('http') ? shot.path : `${base}${shot.path}`;
    const response = await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
    await new Promise((resolve) => setTimeout(resolve, shot.wait || 1200));
    const file = path.join(out, `${shot.name}.png`);
    await page.screenshot({ path: file, fullPage: !!shot.full });
    const title = await page.title();
    const body = (await page.evaluate(() => document.body.innerText || '')).slice(0, 80);
    results.shots.push({ name: shot.name, status: response ? response.status() : 0, title, body });
    console.log(`截图 ${shot.name}｜HTTP ${response ? response.status() : 0}｜${title}`);
  }

  for (const pdf of job.pdfs || []) {
    if (pdf.mobile) {
      await page.setViewport({ width: 414, height: 896, deviceScaleFactor: 2, isMobile: true });
    } else {
      await page.setViewport({ width: 1240, height: 1754, deviceScaleFactor: 2 });
    }
    const url = `${base}/printview?doctype=${encodeURIComponent(pdf.doctype)}` +
      `&name=${encodeURIComponent(pdf.docname)}&format=${encodeURIComponent(pdf.format || 'Standard')}` +
      `&no_letterhead=${pdf.letterhead ? 0 : 1}`;
    const response = await page.goto(url, { waitUntil: 'networkidle2', timeout: 90000 });
    await new Promise((resolve) => setTimeout(resolve, 900));
    const file = path.join(out, `${pdf.name}.pdf`);
    await page.pdf({ path: file, format: 'A4', printBackground: true, margin: { top: '8mm', bottom: '8mm', left: '8mm', right: '8mm' } });
    const buffer = fs.readFileSync(file);
    const pages = (buffer.toString('latin1').match(/\/Type\s*\/Page[^s]/g) || []).length;
    results.pdfs.push({ name: pdf.name, doctype: pdf.doctype, docname: pdf.docname, pages, bytes: buffer.length, status: response.status() });
    console.log(`PDF ${pdf.name}｜${pdf.doctype} ${pdf.docname}｜${pages} 页｜${Math.round(buffer.length / 1024)} KB`);
  }

  fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify(results, null, 2));
  await browser.close();
}

main().catch((error) => {
  console.error('采集失败：', error.message);
  process.exit(1);
});
