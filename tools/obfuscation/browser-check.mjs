import fs from 'node:fs';
import assert from 'node:assert/strict';
import {JSDOM, VirtualConsole} from 'jsdom';

for (const file of process.argv.slice(2)) {
  const errors = [];
  const console = new VirtualConsole();
  console.on('jsdomError', error => errors.push(error));
  const dom = new JSDOM(fs.readFileSync(file, 'utf8'), {
    url: 'https://example.test/i/token/sub', runScripts: 'dangerously',
    pretendToBeVisual: true, virtualConsole: console,
    beforeParse(window) {
      window.fetch = async () => ({ok: true, status: 200,
        json: async () => ({authenticated: false})});
    },
  });
  await new Promise(resolve => dom.window.addEventListener('load', resolve));
  await new Promise(resolve => setTimeout(resolve, 30));
  assert.deepEqual(errors.map(error => error.message), [], file);
  if (dom.window.document.querySelector('#qrPlate')) {
    const svg = dom.window.document.querySelector('#qrPlate svg');
    assert.ok(svg, 'Subscription script must render the QR SVG');
    assert.ok(svg.querySelectorAll('rect').length > 100, 'QR SVG must contain encoded modules');
  } else {
    assert.match(dom.window.document.querySelector('#app').innerHTML, /Sign in/);
    assert.equal(typeof dom.window.document.querySelector('#go').onclick, 'function');
  }
  dom.window.close();
}
process.stdout.write('Browser smoke checks passed\n');
