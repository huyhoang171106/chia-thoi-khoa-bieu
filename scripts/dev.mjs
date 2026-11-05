import { spawn } from 'node:child_process';
const python = process.platform === 'win32' ? 'python' : 'python3';
const server = spawn(python, ['-X', 'utf8', '-m', 'server.app'], { stdio: 'inherit' });
server.on('error', () => { console.error(`Không chạy được ${python}. Hãy cài Python 3.10 trở lên.`); process.exit(1); });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => { server.kill(); process.exit(); });
server.on('exit', code => process.exit(code || 0));
