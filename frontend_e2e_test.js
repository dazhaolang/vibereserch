const { chromium } = require('playwright');

async function testFrontendApp() {
  console.log('🚀 开始前端应用端到端测试...\n');

  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-web-security', '--disable-features=VizDisplayCompositor', '--no-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
  });

  const page = await context.newPage();

  // 监听控制台日志和错误
  const consoleMessages = [];
  const errors = [];

  page.on('console', msg => {
    consoleMessages.push({
      type: msg.type(),
      text: msg.text(),
      timestamp: new Date().toISOString()
    });
  });

  page.on('pageerror', error => {
    errors.push({
      message: error.message,
      stack: error.stack,
      timestamp: new Date().toISOString()
    });
  });

  // 监听网络请求
  const networkRequests = [];
  page.on('request', request => {
    networkRequests.push({
      url: request.url(),
      method: request.method(),
      resourceType: request.resourceType()
    });
  });

  const networkResponses = [];
  page.on('response', response => {
    networkResponses.push({
      url: response.url(),
      status: response.status(),
      statusText: response.statusText()
    });
  });

  try {
    console.log('📋 测试1: 访问前端主页...');

    // 访问前端主页
    const response = await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    if (!response) {
      throw new Error('无法获取页面响应');
    }

    console.log(`✅ 页面响应状态: ${response.status()}`);
    console.log(`📄 页面URL: ${page.url()}`);

    // 等待页面完全加载
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    console.log('\n📋 测试2: 检查页面基本元素...');

    // 获取页面标题
    const title = await page.title();
    console.log(`📝 页面标题: ${title}`);

    // 检查页面是否包含React根元素
    const reactRoot = await page.$('#root');
    console.log(`⚛️  React根元素: ${reactRoot ? '✅ 存在' : '❌ 不存在'}`);

    // 获取页面内容
    const bodyText = await page.textContent('body');
    console.log(`📊 页面内容长度: ${bodyText ? bodyText.length : 0} 字符`);

    // 检查是否有明显的错误信息
    const errorElements = await page.$$('text=/error|错误|failed|失败/i');
    console.log(`🚫 错误信息数量: ${errorElements.length}`);

    console.log('\n📋 测试3: 验证前端与后端API连接...');

    // 检查API请求
    const apiRequests = networkRequests.filter(req =>
      req.url.includes('localhost:8000') || req.url.includes('/api/')
    );
    console.log(`🔗 API请求数量: ${apiRequests.length}`);

    if (apiRequests.length > 0) {
      console.log('🌐 API请求详情:');
      apiRequests.forEach((req, index) => {
        console.log(`  ${index + 1}. ${req.method} ${req.url}`);
      });
    }

    // 检查API响应
    const apiResponses = networkResponses.filter(res =>
      res.url.includes('localhost:8000') || res.url.includes('/api/')
    );
    console.log(`📡 API响应数量: ${apiResponses.length}`);

    if (apiResponses.length > 0) {
      console.log('📊 API响应状态:');
      apiResponses.forEach((res, index) => {
        const status = res.status >= 200 && res.status < 300 ? '✅' : '❌';
        console.log(`  ${index + 1}. ${status} ${res.status} ${res.url}`);
      });
    }

    console.log('\n📋 测试4: 基本UI交互测试...');

    // 查找可交互元素
    const buttons = await page.$$('button');
    const inputs = await page.$$('input');
    const links = await page.$$('a');

    console.log(`🔘 按钮数量: ${buttons.length}`);
    console.log(`📝 输入框数量: ${inputs.length}`);
    console.log(`🔗 链接数量: ${links.length}`);

    // 尝试基本交互（如果有按钮的话）
    if (buttons.length > 0) {
      try {
        const firstButton = buttons[0];
        const buttonText = await firstButton.textContent();
        console.log(`🖱️  尝试点击第一个按钮: "${buttonText}"`);
        await firstButton.click();
        await page.waitForTimeout(1000);
        console.log('✅ 按钮点击成功');
      } catch (clickError) {
        console.log(`⚠️  按钮点击失败: ${clickError.message}`);
      }
    }

    console.log('\n📋 测试5: 检查控制台错误和警告...');

    // 分析控制台消息
    const errorMessages = consoleMessages.filter(msg => msg.type === 'error');
    const warningMessages = consoleMessages.filter(msg => msg.type === 'warning');
    const infoMessages = consoleMessages.filter(msg => msg.type === 'info' || msg.type === 'log');

    console.log(`🚫 错误数量: ${errorMessages.length}`);
    console.log(`⚠️  警告数量: ${warningMessages.length}`);
    console.log(`ℹ️  信息数量: ${infoMessages.length}`);

    if (errorMessages.length > 0) {
      console.log('\n🚨 控制台错误详情:');
      errorMessages.forEach((msg, index) => {
        console.log(`  ${index + 1}. ${msg.text}`);
      });
    }

    if (warningMessages.length > 0) {
      console.log('\n⚠️  控制台警告详情:');
      warningMessages.slice(0, 5).forEach((msg, index) => {
        console.log(`  ${index + 1}. ${msg.text}`);
      });
      if (warningMessages.length > 5) {
        console.log(`  ... 还有 ${warningMessages.length - 5} 个警告`);
      }
    }

    // 页面错误
    if (errors.length > 0) {
      console.log('\n💥 页面JavaScript错误:');
      errors.forEach((error, index) => {
        console.log(`  ${index + 1}. ${error.message}`);
      });
    }

    // 截图
    console.log('\n📸 保存页面截图...');
    await page.screenshot({
      path: 'frontend_test_screenshot.png',
      fullPage: true
    });
    console.log('✅ 截图已保存为 frontend_test_screenshot.png');

    console.log('\n📊 测试总结:');
    console.log('='.repeat(50));

    const isHealthy = response.status() === 200 &&
                     errorMessages.length === 0 &&
                     errors.length === 0 &&
                     reactRoot !== null;

    console.log(`🎯 整体健康状态: ${isHealthy ? '✅ 健康' : '⚠️  需要关注'}`);
    console.log(`📊 页面加载: ${response.status() === 200 ? '✅ 成功' : '❌ 失败'}`);
    console.log(`⚛️  React应用: ${reactRoot ? '✅ 正常' : '❌ 异常'}`);
    console.log(`🌐 API连接: ${apiResponses.length > 0 ? '✅ 有连接' : '⚠️  无连接'}`);
    console.log(`🚫 JavaScript错误: ${errors.length === 0 ? '✅ 无错误' : `❌ ${errors.length}个错误`}`);
    console.log(`⚠️  控制台警告: ${warningMessages.length === 0 ? '✅ 无警告' : `⚠️  ${warningMessages.length}个警告`}`);

    return {
      success: true,
      status: response.status(),
      title,
      hasReactRoot: !!reactRoot,
      apiRequests: apiRequests.length,
      apiResponses: apiResponses.length,
      errors: errors.length,
      warnings: warningMessages.length,
      uiElements: {
        buttons: buttons.length,
        inputs: inputs.length,
        links: links.length
      }
    };

  } catch (error) {
    console.error('💥 测试过程中出现错误:', error.message);

    // 尝试截图错误状态
    try {
      await page.screenshot({
        path: 'frontend_error_screenshot.png',
        fullPage: true
      });
      console.log('📸 错误状态截图已保存');
    } catch (screenshotError) {
      console.log('📸 无法保存错误状态截图');
    }

    return {
      success: false,
      error: error.message,
      errors: errors.length,
      warnings: consoleMessages.filter(msg => msg.type === 'warning').length
    };

  } finally {
    await browser.close();
    console.log('\n🔚 浏览器已关闭，测试完成');
  }
}

// 运行测试
testFrontendApp()
  .then(result => {
    console.log('\n✅ 测试结果:', JSON.stringify(result, null, 2));
    process.exit(0);
  })
  .catch(error => {
    console.error('❌ 测试失败:', error);
    process.exit(1);
  });