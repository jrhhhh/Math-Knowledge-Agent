import { chromium } from 'playwright';

const base = process.env.WEB_URL || 'http://127.0.0.1:5500';
const api = process.env.API_URL || 'http://127.0.0.1:8000';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
try {
  await page.addInitScript(value => { window.MATH_AGENT_API = value; }, api);
  await page.goto(`${base}/formula-test.html`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('#status')?.textContent.includes('渲染完成'));
  const formulaCount = await page.locator('mjx-container').count();
  if (formulaCount < 5) throw new Error(`expected at least 5 rendered formulas, got ${formulaCount}`);
  await page.goto(`${base}/index.html`, { waitUntil: 'networkidle' });
  if (!(await page.getByRole('heading', { name: '推理结果' }).isVisible())) throw new Error('main response panel missing');
  await page.waitForSelector('#conversationList .conversation-item');
  if (!(await page.getByRole('button', { name: '新建对话' }).isVisible())) throw new Error('conversation workspace missing');
  await page.getByRole('button', { name: '新建对话' }).click();
  await page.waitForFunction(() => document.querySelectorAll('#conversationList .conversation-item').length >= 2);
  const graphConcept = await page.evaluate(async () => {
    const response = await fetch(`${window.MATH_AGENT_API}/concepts/?name=%E7%B4%A7%E8%87%B4%E6%80%A7%E5%86%92%E7%83%9F%E6%B5%8B%E8%AF%95&description=%E7%94%A8%E4%BA%8E%E9%AA%8C%E8%AF%81%E5%9B%BE%E8%B0%B1%E4%BA%A4%E4%BA%92%E3%80%82&field=%E6%8B%93%E6%89%91%E5%AD%A6`, { method: 'POST' });
    if (!response.ok) throw new Error('unable to create smoke-test concept');
    return response.json();
  });
  await page.locator('#conceptSearch').fill('紧致性冒烟测试');
  await page.locator('#conceptSearchButton').click();
  await page.waitForFunction(() => document.querySelector('#conceptSearchResults')?.classList.contains('is-visible'));
  if (!(await page.locator('#conceptSearchResults [data-concept-id]').count())) throw new Error('persisted concept search returned no result');
  await page.locator('#conceptSearchResults [data-concept-id]').first().click();
  await page.waitForFunction(() => document.querySelector('#graphStatus')?.textContent.includes('已加载'));
  await page.evaluate(concept => renderGraph({
    nodes: [{ id: concept.id, name: concept.name, type: concept.type, field: concept.field, description: concept.description }],
    edges: [],
  }), graphConcept);
  await page.locator('#graphCanvas .graph-node').click();
  await page.waitForFunction(() => document.querySelector('#graphConceptCard')?.textContent.includes('紧致性冒烟测试'));
  if (await page.locator('#graphConceptCard.hidden').count()) throw new Error('graph concept card did not open');
  if (!(await page.locator('#graphConceptCard').textContent()).includes('推荐学习顺序')) throw new Error('learning path missing from graph concept card');
  if (await page.locator('[data-learning-concept]').count()) throw new Error('learning path still exposes manual mastery controls');
  if (!(await page.locator('#graphConceptCard').textContent()).includes('掌握状态只由审核后的作答证据更新')) throw new Error('evidence-driven mastery notice missing');
  console.log(`Browser smoke passed: ${formulaCount} MathJax formulas rendered.`);
} finally {
  await browser.close();
}
