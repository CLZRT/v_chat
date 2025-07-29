import os
import re
import yaml
import logging

# 使用标准 logging，而不是我们自定义的 logger，因为配置模块应该是最先加载的
log = logging.getLogger(__name__)
_config_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'config.yaml'
)

# 将之前的加载逻辑封装成一个“私有”函数
def _load_config_with_env(path='config.yaml'):
    """
    加载 YAML 配置，并解析其中的环境变量占位符。
    这个函数现在是模块的内部实现。
    """
    if not os.path.exists(path):
        log.error(f"配置文件 '{path}' 不存在。应用无法启动。")
        # 在无法加载配置时，通常应该直接退出程序
        raise FileNotFoundError(f"Config file not found: {path}")

    # 正则表达式用于匹配 ${VAR} 或 ${VAR:default}
    env_pattern = re.compile(r'\$\{(?P<name>[^}:]+)(?::(?P<default>[^}]+))?\}')

    def env_constructor(loader, node):
        """自定义一个 YAML 构造器来处理环境变量"""
        value = loader.construct_scalar(node)
        match = env_pattern.fullmatch(value)
        if not match:
            return value

        env_var_name = match.group('name')
        default_value = match.group('default')

        # 优先使用环境变量，否则使用默认值
        return os.getenv(env_var_name, default_value)

    loader = yaml.SafeLoader
    loader.add_constructor('!ENV', env_constructor)

    try:
        with open(path, 'r', encoding='utf-8') as file:
            # 使用 yaml.load 而不是 safe_load 是为了让自定义的 constructor 生效
            # 我们通过限制 constructor 的行为来保证安全
            config_data = yaml.load(file, Loader=loader)
            return config_data
    except yaml.YAMLError as e:
        log.error(f"解析 YAML 文件 '{path}' 时出错: {e}")
        raise


# ---- 关键部分在这里 ----
# 在模块被导入时，立即执行加载函数，并将结果存储在一个全局变量中
# 这个代码块在整个应用的生命周期中只会执行一次！
settings = _load_config_with_env(_config_file_path)

log.info("应用配置加载成功。")