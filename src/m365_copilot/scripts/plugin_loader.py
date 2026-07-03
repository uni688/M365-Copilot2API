"""自动加载自定义工具。

扫描 ~/.m365-copilot/tools/ 目录下的 .py 文件并导入，
文件中通过 @provider.register() 装饰器的函数会自动注册。
"""
import os
import sys
import importlib.util
import logging

TOOLS_DIR = os.path.expanduser("~/.m365-copilot/tools")

logger = logging.getLogger(__name__)


def load_user_tools():
    if not os.path.isdir(TOOLS_DIR):
        return 0

    loaded = 0
    for fname in sorted(os.listdir(TOOLS_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.join(TOOLS_DIR, fname)
        try:
            spec = importlib.util.spec_from_file_location(
                f"user_tool_{fname[:-3]}", fpath
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            loaded += 1
        except Exception as e:
            logger.warning(f"加载工具 {fname} 失败: {e}")

    if loaded:
        logger.info(f"已加载 {loaded} 个自定义工具文件")
    return loaded
