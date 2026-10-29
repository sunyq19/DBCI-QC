"""Start/reuse the local workbench without a terminal remaining open."""
from pathlib import Path
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

REPO = Path(__file__).resolve().parents[1]
SERVICE = 'ephys-qc-modular-workbench'


def health(url):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url + 'api/v1/health', timeout=2) as response:
            return json.load(response).get('service') == SERVICE
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description='启动本机 EEG 模块化质控工作台')
    parser.add_argument('--config', type=Path, default=REPO / '.local/workbench.json')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--open', action='store_true', help='在系统浏览器中打开')
    args = parser.parse_args()
    config_path = args.config.resolve()
    if not config_path.exists():
        raise SystemExit('尚未配置数据和运行环境。请按 apps/workbench/README.md 创建 .local/workbench.json。')
    settings = json.loads(config_path.read_text())
    runtime = Path(settings['data_dir'])
    runtime.mkdir(parents=True, exist_ok=True)
    url = f'http://127.0.0.1:{settings.get("port", 8769)}/'
    pidfile = runtime / 'server.pid'
    if args.stop:
        if not pidfile.exists():
            raise SystemExit('没有本启动器记录的服务进程。')
        pid = int(pidfile.read_text())
        try:
            command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:
            print('服务已停止。')
            return
        if str(REPO / 'apps/workbench/server.py').encode() not in command or str(config_path).encode() not in command:
            raise SystemExit('进程不属于本工作台，未执行停止。')
        os.kill(pid, signal.SIGTERM)
        print('已请求停止本工作台。')
        return
    ready = health(url)
    if args.status:
        print(('运行中：' if ready else '未运行：') + url)
        return
    if not ready:
        with (runtime / 'server.log').open('a', encoding='utf-8') as log:
            p = subprocess.Popen([settings['python'], str(REPO / 'apps/workbench/server.py'), '--config', str(config_path)],
                                 cwd=REPO, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        pidfile.write_text(str(p.pid))
        for _ in range(60):
            if health(url):
                break
            if p.poll() is not None:
                raise SystemExit('启动失败，请查看 ' + str(runtime / 'server.log'))
            time.sleep(0.25)
        else:
            raise SystemExit('服务尚未就绪，请查看 ' + str(runtime / 'server.log'))
    print(url)
    if args.open:
        import webbrowser
        webbrowser.open(url)


if __name__ == '__main__':
    main()
