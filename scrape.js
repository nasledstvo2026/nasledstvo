const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    locale: 'ru-RU'
  });
  const page = await context.newPage();
  
  // Try tbank slug first, then tinkoff
  for (const slug of ['tbank', 'tinkoff']) {
    const url = `https://www.banki.ru/services/responses/bank/${slug}/?text=%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE&type=all&date_from=01.01.2025&date_to=01.06.2026`;
    
    console.log(`\nTrying slug: ${slug}`);
    try {
      await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(5000);
      
      const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 15000));
      
      if (bodyText.includes('наследств') || bodyText.includes('отзыв') || bodyText.includes('натуральный')) {
        console.log(`SLUG ${slug} - HAS CONTENT`);
        console.log(bodyText);
      } else {
        console.log(`SLUG ${slug} - page loaded but no matching content. First 500 chars:`);
        console.log(bodyText.substring(0, 500));
      }
    } catch (e) {
      console.log(`SLUG ${slug} ERROR:`, e.message.substring(0, 200));
    }
  }
  
  await browser.close();
})();
