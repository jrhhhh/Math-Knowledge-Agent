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
  await page.waitForSelector('#conversationList');
  if (!(await page.getByRole('button', { name: '新建对话' }).isVisible())) throw new Error('conversation workspace missing');
  await page.getByRole('button', { name: '新建对话' }).click();
  await page.waitForFunction(() => Boolean(localStorage.getItem('math-agent-conversation-id')));
  if (await page.locator('#conversationList .conversation-item').filter({ hasText: '0 条消息' }).count()) {
    throw new Error('empty conversations should not appear in history');
  }
  const graphConcept = await page.evaluate(async () => {
    const name = '紧致性冒烟测试';
    const field = '拓扑学';
    const search = await fetch(`${window.MATH_AGENT_API}/concepts/search?q=${encodeURIComponent(name)}&limit=100`);
    if (!search.ok) throw new Error('unable to search smoke-test concept');
    const matches = (await search.json()).items || [];
    const existing = matches.find(item => item.name === name && item.field === field);
    if (existing) return existing;
    const response = await fetch(`${window.MATH_AGENT_API}/concepts/?name=${encodeURIComponent(name)}&description=${encodeURIComponent('用于验证图谱交互。')}&field=${encodeURIComponent(field)}`, { method: 'POST' });
    if (!response.ok) throw new Error('unable to create smoke-test concept');
    return response.json();
  });
  await page.getByRole('link', { name: '图谱', exact: true }).click();
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
  if (!(await page.locator('#graphConceptCard').textContent()).includes('推荐学习')) throw new Error('learning path missing from graph concept card');
  if (await page.locator('[data-learning-concept]').count()) throw new Error('learning path still exposes manual mastery controls');
  if (!(await page.locator('#graphConceptCard').textContent()).includes('掌握状态只由审核后的作答证据更新')) throw new Error('evidence-driven mastery notice missing');
  await page.getByRole('link', { name: '实验', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#labStatus')?.textContent.includes('计算完成'), null, { timeout: 20000 });
  if (!(await page.locator('#labResult').textContent()).includes('双侧导数 = 2')) throw new Error('symbolic derivative missing');
  if (await page.locator('#labFunction option').count() !== 31) throw new Error('common function catalog incomplete');
  await page.getByRole('button', { name: '高等代数', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#labMatrixResults')?.textContent.includes('Cayley'), null, { timeout: 20000 });
  if (!(await page.locator('#labMatrixResults').textContent()).includes('实数域可对角化：是')) throw new Error('symmetric matrix results missing');
  if (await page.locator('#labMatrixResults details[open] tbody tr').count() !== 3) throw new Error('principal minors incomplete');
  await page.locator('#labMatrixPreset').selectOption('rotation');
  await page.waitForFunction(() => document.querySelector('#labMatrixResults')?.textContent.includes('实数域可对角化：否'), null, { timeout: 20000 });
  if (!(await page.locator('#labResult').textContent()).includes('没有实特征方向')) throw new Error('complex eigenvalue example incorrectly plots real eigenvectors');
  await page.locator('#labMatrixPreset').selectOption('four');
  await page.waitForFunction(() => document.querySelector('#labMatrixResults details[open] tbody')?.children.length === 15, null, { timeout: 20000 });
  await page.getByRole('button', { name: '积分', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#labResult')?.textContent.includes('定积分 = 0.3333333'), null, { timeout: 20000 });
  await page.locator('#labFunction').selectOption('reciprocal');
  await page.locator('#labExpression').fill('1/(x-1.5)');
  await page.getByRole('button', { name: '计算并绘图' }).click();
  await page.waitForFunction(() => document.querySelector('#labStatus')?.textContent.includes('跨越'), null, { timeout: 20000 });
  if (await page.locator('#labPlot polyline').count()) throw new Error('invalid integral retained stale plot');
  console.log(`Browser smoke passed: ${formulaCount} MathJax formulas rendered.`);
} finally {
  await browser.close();
}
