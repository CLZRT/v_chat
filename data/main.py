import atexit
import threading

import log.logger as logger
import time
import config.config as config
import data.format as fm
from data.collect import KeyMouseData, WindowsData

config = config.settings
logger.setup_logger(config['data']['log_name'])
class DataCollector:
    def __init__(self):
        self.collect_windows = WindowsData(second=config['data']['collect']['window_second'])
        self.collect_keyMouses = KeyMouseData()
        self.format_windows = None

    # 传入收集容器,进行信息收集
    def _collect(self):
        if self.collect_windows is None:
            self.collect_windows = WindowsData(second=config['data']['collect']['window_second'])
        if self.collect_keyMouses is None:
            self.collect_keyMouses = KeyMouseData()
        self.collect_windows.start_collect()
        self.collect_keyMouses.collect_events()

    # 传入收集信息,进行信息整理
    def _sort(self):
        if self.format_windows is None:
            self.format_windows= fm.SortedDatas(minute=config['data']['format']['window_minute'],
                                                win_datas=self.collect_windows, km_datas=self.collect_keyMouses)
        self.format_windows.start_sort()
        return

    def start(self):
        self._collect()
        time.sleep(config['data']['collect']['window_second'])
        self._sort()
    def stop(self):
        self.collect_windows.stop_collect()
        self.collect_keyMouses.stop_collect()
        self.format_windows.stop_sort()


