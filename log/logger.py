# logger_config.py

import logging
import os
import sys

# 自定义一个 Formatter，用于根据日志级别决定输出格式
class ConditionalFormatter(logging.Formatter):
    """
    一个可以根据日志级别应用不同格式的 Formatter。
    """
    # 为不同级别定义格式
    # %(asctime)s - 时间
    # %(levelname)s - 日志级别
    # %(message)s - 日志消息
    # %(filename)s - 文件名
    # %(lineno)d - 行号
    INFO_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    WARNING_FORMAT = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

    def __init__(self):
        # 调用父类的构造函数，但不传递格式字符串，因为我们将动态决定它
        super().__init__(fmt="%(levelno)d: %(msg)s", datefmt=None, style='%')

    def format(self, record):
        # 复制一份 record，以防原始 record 被修改
        original_record = record.__dict__.copy()

        # 根据日志级别选择格式
        if record.levelno >= logging.WARNING:
            self._style._fmt = self.WARNING_FORMAT
        else:
            self._style._fmt = self.INFO_FORMAT

        # 调用父类的 format 方法来执行实际的格式化
        result = super().format(record)

        # 恢复原始 record 的状态（虽然在这个实现中不是严格必要，但这是个好习惯）
        record.__dict__ = original_record

        return result


def setup_logger(log_name,):
    """
    初始化并配置一个全局 logger。

    :param log_file_path: 日志文件的路径。
    :return: 配置好的 logger 实例。
    """
    # 1. 获取一个 logger 实例（如果已存在，则返回现有实例）
    #    我们给它一个名字，比如 'my_app_logger'
    if log_name is None or type(log_name) != str:
        raise TypeError("log_name error")

    log_file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        log_name+"_app.log"
                                 )
    if not os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'w') as file:
                pass  # 不写入内容，仅创建文件
            print(f"文件 {log_file_path} 创建成功")
        except Exception as e:
            print(f"创建文件失败: {e}")
    logger = logging.getLogger(log_name)

    # 2. 设置 logger 的最低处理级别。设置为 DEBUG 可以捕获所有级别的日志。
    #    真正的过滤将在 Handlers 中完成。
    logger.setLevel(logging.DEBUG)

    # 3. 防止日志消息向上传递给 root logger，避免重复打印。
    #    这是至关重要的一步！
    logger.propagate = False

    # 4. 如果 logger 已经有 handlers，说明已经配置过了，直接返回，避免重复添加 handler。
    if logger.hasHandlers():
        return logger

    # 5. 创建自定义的 Formatter
    custom_formatter = ConditionalFormatter()

    # 6. 创建控制台 Handler (StreamHandler)
    #    只显示 INFO 及以上级别的信息
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(custom_formatter)

    # 7. 创建文件 Handler (FileHandler)
    #    记录所有 DEBUG 及以上级别的信息到文件
    file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(custom_formatter)

    # 8. 将 Handlers 添加到 Logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger