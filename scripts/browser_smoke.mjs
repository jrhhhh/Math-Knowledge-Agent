import { chromium } from 'playwright';

const base = process.env.WEB_URL || 'http://127.0.0.1:5500';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
try {
  await page.goto(`${base}/formula-test.html`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('#status')?.textContent.includes('渲染完成'));
  const formulaCount = await page.locator('mjx-container').count();
  if (formulaCount < 5) throw new Error(`expected at least 5 rendered formulas, got ${formulaCount}`);
  await page.goto(`${base}/index.html`, { waitUntil: 'networkidle' });
  if (!(await page.getByRole('heading', { name: '推理结果' }).isVisible())) throw new Error('main response panel missing');
  console.log(`Browser smoke passed: ${formulaCount} MathJax formulas rendered.`);
} finally {
  await browser.close();
}
