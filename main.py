"""mai_study_code 独立进程入口。

作为独立 Supervisor 进程运行，不依赖 MaiBot 插件体系。
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

# ── 把当前目录加入 path，确保模块内导入正常工作 ──
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mai-study-code.main")


def main() -> None:
    """主入口。"""
    # 读取配置
    from agent.config import AgentConfig

    config_path = os.path.join(_THIS_DIR, "agent_config.toml")
    # fallback: 如果没有 agent_config.toml 则尝试 config.toml
    if not os.path.exists(config_path):
        config_path = os.path.join(_THIS_DIR, "config.toml")
    config = AgentConfig.load(config_path)

    # 配置日志级别
    logging.getLogger().setLevel(
        logging.DEBUG if config.debug else logging.INFO
    )

    # 启动 Web 服务
    from agent.web_server import AgentWebServer

    web_server = AgentWebServer(config)
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        """优雅关闭。"""
        logger.info("收到停止信号，正在关闭...")
        shutdown_event.set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 注册信号处理
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows 不支持 add_signal_handler

    try:
        loop.run_until_complete(web_server.start())
        logger.info(f"mai_study_code 独立进程已启动，端口: {web_server.port}")
        # 等待关闭信号
        loop.run_until_complete(shutdown_event.wait())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("正在停止 mai_study_code...")
        loop.run_until_complete(web_server.stop())
        loop.close()
        logger.info("mai_study_code 已停止")


if __name__ == "__main__":
    main()
