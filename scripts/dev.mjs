import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
mkdirSync('build', { recursive: true });
const compile = spawn('javac', ['-encoding', 'UTF-8', '-d', 'build', 'src/Main.java', 'src/Auth.java', 'src/CpScheduler.java', 'src/SchoolExport.java'], { stdio: 'inherit' });
compile.on('exit', code => {
  if (code !== 0) process.exit(code || 1);
  const server = spawn('java', ['-cp', 'build', 'Main'], { stdio: 'inherit' });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => { server.kill(); process.exit(); });
  server.on('exit', code => process.exit(code || 0));
});
