/* Optional browser regression suite. Install Playwright separately; the builder stays dependency-free. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'argument-browser-'));
const output = path.resolve(process.env.ARGMAP_SCREENSHOTS || path.join(tmp, 'screenshots'));
fs.mkdirSync(output, { recursive: true });
const graph = JSON.parse(fs.readFileSync(path.join(root, 'examples/tutorial-graph.json'), 'utf8'));
graph.figures = { preview: { label: 'Example figure', uri: 'data:image/png;base64,' + fs.readFileSync(path.join(root, 'docs/overview.png')).toString('base64') } };
graph.nodes[0].figure = 'preview';
graph.nodes[0].label_zh = '\u90e8\u7f72\u4fe1\u5fc3';
graph.nodes[0].detail_zh = '\u90e8\u7f72\u9700\u8981\u53ef\u4fe1\u7684\u7f6e\u4fe1\u5ea6\u3002';
const json = path.join(tmp, 'graph.json'), html = path.join(tmp, 'graph.html');
fs.writeFileSync(json, JSON.stringify(graph));
const built = spawnSync(process.env.PYTHON || 'python3', [path.join(root, 'scripts/build_graph.py'), json, '-o', html, '--source', path.join(root, 'examples/tutorial-paper.txt')], { encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
assert.equal(built.status, 0, built.stdout + built.stderr);
const markup = fs.readFileSync(html, 'utf8');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ARGMAP_BROWSER ? { executablePath: process.env.ARGMAP_BROWSER } : {}) });
  try {
    for (const width of [1440, 768, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
      const page = await context.newPage();
      const errors = [], requests = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('request', req => { if (/^https?:/.test(req.url())) requests.push(req.url()); });
      await page.setContent(markup);
      await page.waitForFunction(() => typeof nodes !== 'undefined' && nodes.every(n => Number.isFinite(n.px)) && nodes.some(n => n.labelA > 0));
      assert.equal(await page.locator('#bt-rotate').getAttribute('aria-pressed'), 'false');
      const pixels = await page.evaluate(() => {
        render(performance.now(), true);
        const pixels = new Uint8Array(glc.width * glc.height * 4);
        gl.readPixels(0, 0, glc.width, glc.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        const colors = new Set();
        for (let i = 0; i < pixels.length; i += 128) colors.add(`${pixels[i]},${pixels[i+1]},${pixels[i+2]}`);
        const labels = ctx.getImageData(0, 0, lbl.width, lbl.height).data;
        return { colors: colors.size, labelPixels: labels.filter((x, i) => i % 4 === 3 && x > 0).length };
      });
      assert(pixels.colors > 10 && pixels.labelPixels > 100, JSON.stringify(pixels));
      await page.screenshot({ path: path.join(output, `graph-${width}.png`) });
      await page.locator('#bt-search').click();
      await page.locator('#search-input').fill('calibration');
      assert(await page.locator('.search-result').count() > 0);
      await page.locator('#search-input').press('ArrowDown');
      await page.locator('#search-input').press('Enter');
      assert(await page.locator('#panel').getAttribute('aria-hidden') === 'false');
      await page.locator('#view-reading').click();
      assert.equal(await page.locator('.read-node').count(), graph.nodes.length);
      assert.equal(await page.evaluate(() => animationFrame), 0);
      const order = await page.locator('.read-node').evaluateAll(rows => rows.map(row => row.dataset.nodeId));
      for (const e of graph.edges.filter(e => e.main)) assert(order.indexOf(e.source) < order.indexOf(e.target));
      assert(await page.locator('.read-node .evidence-status').count() === graph.nodes.length);
      await page.locator('.read-node img').first().scrollIntoViewIfNeeded();
      await page.waitForFunction(() => [...document.querySelectorAll('.read-node img')].every(i => i.complete && i.naturalWidth > 0));
      const dimensions = await page.evaluate(() => ({ viewport: innerWidth, scroll: document.getElementById('reader').scrollWidth }));
      assert(dimensions.scroll <= dimensions.viewport + 1, JSON.stringify(dimensions));
      await page.screenshot({ path: path.join(output, `reading-${width}.png`) });
      await page.locator('#spine-next').click();
      assert.equal(await page.locator('.read-node[data-selected="true"]').count(), 1);
      await page.locator('#bt-settings').click();
      await page.locator('#st-lang button[data-v="zh"]').click();
      assert(await page.locator('#reader-nodes').innerText().then(text => text.includes('\u90e8\u7f72\u4fe1\u5fc3')));
      await page.locator('#st-lang button[data-v="en"]').click();
      await page.locator('#view-graph').click();
      if (width === 1440) {
        await page.locator('#bt-settings').click();
        for (let i = 0; i < 3; i++) {
          const downloaded = page.waitForEvent('download');
          await page.locator('#st-png').click();
          const download = await downloaded;
          const file = path.join(tmp, `export-${i}.png`);
          await download.saveAs(file);
          assert(fs.statSync(file).size > 1000);
        }
      }
      assert.deepEqual(errors, []);
      assert.deepEqual(requests, []);
      await context.close();
      console.log(`PASS: graph, reading, evidence, search, language, figures at ${width}px`);
    }
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type, ...args) {
        return /webgl/.test(type) ? null : original.call(this, type, ...args);
      };
    });
    await page.goto('about:blank');
    await page.setContent(markup);
    assert(await page.locator('#reader').isVisible());
    assert.equal(await page.locator('.read-node').count(), graph.nodes.length);
    assert(await page.locator('#view-graph').isDisabled());
    console.log('PASS: no-WebGL reading fallback');
    await context.close();
    console.log(`Screenshots: ${output}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
