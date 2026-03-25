const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PORT = 3000;
const API_PORT = process.env.API_PORT || 2026;

function checkApiServer() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${API_PORT}/health`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForApi(timeout = 60) {
  console.log(`等待 API 服务器 (端口 ${API_PORT})...`);
  const start = Date.now();
  while (Date.now() - start < timeout * 1000) {
    if (await checkApiServer()) {
      console.log('API 服务器已就绪');
      return true;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  console.warn('API 服务器未响应，继续启动...');
  return false;
}

async function startFrontend() {
  const basePath = path.dirname(process.execPath || __filename);
  const frontendDir = path.join(basePath, 'app');

  console.log(`前端目录: ${frontendDir}`);

  const nextServer = path.join(frontendDir, 'server.js');
  if (!require('fs').existsSync(nextServer)) {
    console.error('Next.js server 未找到!');
    console.error(`期望路径: ${nextServer}`);
    process.exit(1);
  }

  console.log(`启动 Next.js 前端 (端口 ${PORT})...`);

  await waitForApi();

  const nextProc = spawn(process.execPath, [nextServer], {
    cwd: frontendDir,
    stdio: 'inherit',
    env: {
      ...process.env,
      PORT: String(PORT),
      HOSTNAME: '127.0.0.1',
      NODE_ENV: 'production'
    }
  });

  nextProc.on('error', (err) => {
    console.error('Next.js 启动失败:', err);
    process.exit(1);
  });

  nextProc.on('exit', (code) => {
    if (code !== 0) {
      console.error(`Next.js 进程退出，代码: ${code}`);
    }
    process.exit(code);
  });

  process.on('SIGINT', () => {
    console.log('收到 SIGINT，关闭...');
    nextProc.kill('SIGINT');
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    console.log('收到 SIGTERM，关闭...');
    nextProc.kill('SIGTERM');
    process.exit(0);
  });

  console.log(`Next.js 前端已启动 http://127.0.0.1:${PORT}`);
}

startFrontend().catch((err) => {
  console.error('启动失败:', err);
  process.exit(1);
});
