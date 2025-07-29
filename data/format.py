import logging
import threading
import time
from collections import Counter
from datetime import datetime

import db.sqlite
from config import config
from data import  schedule


class MemorySorted:
    def __init__(self):
        self.avgMemoryPercent = 0
        self.avgRss = 0
        self.avgVms = 0
        self.avgPeakWSet = 0
        self.avgNumPageFault = 0
        self.statsCount = 0
    def update(self,original_memory_usage):
        if not original_memory_usage:
            logger.warning("original_memory_usage is null")
            return
        if self.statsCount == 0:
            self.avgMemoryPercent = original_memory_usage.memoryPercent
            self.avgRss = original_memory_usage.rss
            self.avgVms = original_memory_usage.vms
            self.avgPeakWSet = original_memory_usage.peakWSet
            self.avgNumPageFault = original_memory_usage.numPageFault
            self.statsCount += 1
            return
        self.calculate_average(original_memory_usage)
    def calculate_average(self,original_memory_usage):
        # todo 计算mem的平均值
        count = self.statsCount
        self.statsCount += 1
        self.avgMemoryPercent = (self.avgMemoryPercent * count + original_memory_usage.memoryPercent) / self.statsCount
        self.avgRss = (self.avgRss * count + original_memory_usage.rss) / self.statsCount
        self.avgVms = (self.avgVms * count + original_memory_usage.vms) / self.statsCount
        self.avgPeakWSet = (self.avgPeakWSet * count + original_memory_usage.peakWSet) / self.statsCount
        self.avgNumPageFault = (self.avgNumPageFault * count + original_memory_usage.numPageFault) / self.statsCount
        return

class IOSorted:
    def __init__(self):
        self.totalRCallNum = 0
        self.totalWCallNum = 0
        self.totalRByteNum = 0
        self.totalWByteNum = 0
    def update(self,original_io_usage):
        if not original_io_usage:
            logger.warning("original_io_usage is null")
            return
        self.totalRCallNum += original_io_usage.RCallNum
        self.totalWCallNum += original_io_usage.WCallNum
        self.totalRByteNum += original_io_usage.RByteNum
        self.totalWByteNum += original_io_usage.WByteNum

class ProcesSorted:
    def __init__(self):
        self.pid = None
        self.name = None
        self.path = None
        self.username = None
        self.status = []
        self.startTime = None
        self.cpuUsage = None
        self.memoryUsage = MemorySorted()
        self.ioUsage = IOSorted()
    def update(self, original_process_infos):
        if not original_process_infos:
            logger.warning("original_process_infos is Null")
            return
        self.status.append(original_process_infos.status)
        # pid为None表示内容为空
        if self.pid is None:
            self.pid = original_process_infos.pid
            self.name = original_process_infos.name
            self.path = original_process_infos.path
            self.username = original_process_infos.username
            self.startTime = original_process_infos.startTime
        # 更新-统计的内存使用情况和io使用情况
        self.memoryUsage.update(original_process_infos.memoryUsage)
        self.ioUsage.update(original_process_infos.ioUsage)

class KeyBoardInfo:
    def __init__(self):
        self.keyPressNum = 0
        self.keyPressList = {}

    def update(self,keyboard_info):
        if not keyboard_info:
            logger.warning("keyboard_info is null")
            return
        self.keyPressNum += keyboard_info.keyPressNum
        self._update_key_list(keyboard_info.keyPressList)

    def _update_key_list(self, key_list):
        if not key_list:
            logger.warning("key_list is null")
            return
        self.keyPressList = dict(Counter(self.keyPressList) +  Counter(key_list))
class MouseInfo:
    def __init__(self):
        self.mouseScrollNum = 0
        self.mouseMoveNum = 0
        self.mouseLeftClickNum = 0
        self.mouseRightClickNum = 0
        self.mouseOtherClickNum = 0
    def update(self, mouse_info):
        if not mouse_info:
            logger.warning("mouse_info is null")
            return
        self.mouseScrollNum += mouse_info.mouseScrollNum
        self.mouseMoveNum += mouse_info.mouseMoveNum
        self.mouseLeftClickNum += mouse_info.mouseLeftClickNum
        self.mouseRightClickNum += mouse_info.mouseRightClickNum
        self.mouseOtherClickNum += mouse_info.mouseOtherClickNum
# 单个窗口的统计信息

def transform_time(unix_time):
    if not unix_time:
        logger.warning("unix_time is null")
        return None
    dt_object = datetime.fromtimestamp(unix_time)
    formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_time


class WindowSorted:
    """
    用于存放整理好的,每一分钟的window信息
    时间以秒为单位
    """
    def __init__(self):
        self.windowHwnd = 0
        self.whichMinute = ""
        self.windowTitles = []
        # pid as key
        self.processInfos = {}
        self.keyboardInfo = KeyBoardInfo()
        self.mouseInfo = MouseInfo()
        self.startTime = ""

        # 担任主窗口时间
        self.mainWindowTime = 0
        # 音频,麦克风,摄像头
        self.mediaUseTime = 0
        self.microUseTime = 0
        self.cameraUseTime = 0

        self.mediaShareTime = 0
        self.microShareTime = 0
        self.cameraShareTime = 0
    def update(self,original_window,original_km_data,):
        if not original_window:
            logger.warning("original_window is null")
            return

        # 第一次信息载入
        if not self.windowHwnd :
            self.whichMinute = datetime.strftime(original_window.whichTime, "%Y-%m-%d %H:%M")
            self.windowHwnd = original_window.windowId
            self.startTime = transform_time(original_window.startTime)
            if original_km_data is not None:
                # 更新键盘信息
                self.keyboardInfo.update(original_km_data.keyboardInfo)
                # 更新鼠标信息
                self.mouseInfo.update(original_km_data.mouseInfo)

        time_second = config['data']['collect']['window_second']
        # 更新主窗口时间
        if original_window.isMainWindow:
            self.update_main_window_time(time_second)
        # 添加窗口标题
        if original_window.windowTitle not in self.windowTitles:
            self.windowTitles.append(original_window.windowTitle)
        # 更新process信息
        for processInfo in original_window.processInfos:
            self.processInfos.setdefault(processInfo.pid, ProcesSorted()).update(processInfo)



        time_second = config['data']['collect']['window_second']
        # 更新各外设使用时间
        if original_window.isUseMedia:
            self.update_media_use_time(time_second)
        if original_window.isUseMicroPhone:
            self.update_micro_use_time(time_second)
        if original_window.isUseCamera:
            self.update_camera_use_time(time_second)
        if original_window.isShareMedia:
            self.update_media_share_time(time_second)
        if original_window.isShareMicroPhone:
            self.update_micro_share_time(time_second)
        if original_window.isShareCamera:
            self.update_camera_share_time(time_second)

    # 更新时间
    def update_main_window_time(self,time_second):
        self.mainWindowTime += time_second
    def update_media_use_time(self,time_second):
        self.mediaUseTime += time_second
    def update_micro_use_time(self,time_second):
        self.microUseTime += time_second
    def update_camera_use_time(self,time_second):
        self.cameraUseTime += time_second
    def update_media_share_time(self,time_second):
        self.mediaShareTime += time_second
    def update_micro_share_time(self,time_second):
        self.microShareTime += time_second
    def update_camera_share_time(self,time_second):
        self.cameraShareTime += time_second

config = config.settings
logger = logging.getLogger(config['data']['log_name'])


# 将设定时间内的window信息组合起来
class SortedDatas:
    def __init__(self,minute,km_datas, win_datas):
        """

        :param minute: 执行频率，分钟为计算单位
        :param km_datas: 键鼠统计信息
        :param win_datas: 窗口统计信息
        """
        # window_hwnd 为 key
        self._lock = threading.Lock()
        self.originalWindowDatas = win_datas
        self.originalKMDatas = km_datas
        self.windows = {}
        self.initiativeUse = False
        self.schedulerManager = schedule.SchedulerManager()
        if type(minute) != int or minute <= 0:
            logger.warning("minute is invalid")
            return
        self.minute = minute



    def merge_data(self):
        """
        合并容器里的original数据到windows
        """
        logger.info("merge_data")
        window_list_list = self.originalWindowDatas.get_and_reset()
        kms_window,kms_count =self.originalKMDatas.get_and_reset()
        # 检查传入参数是否为空
        if not window_list_list:
            logger.warning("windows_list_list is Empty")
            return None
        # kms_count不为0，表示用户最近1分钟内有碰过鼠标or键盘
        if  kms_count > 0:
            self.initiativeUse = True

        with self._lock:
            # 将windows_list_list 变为 windows_list,
            for windows_list in window_list_list:
                for window in windows_list:
                    # window为窗口列表;km_window[window.windowId]表示为km_info
                    # 有些窗口，没有输入输出，就正常处理就好,怕就怕在 没有对应key会阻塞
                    self.windows.setdefault(window.windowId, WindowSorted()).update(window, kms_window.get(window.windowId))



        logger.info("windows_list_list's merge is finish")
        return None


    def _get_and_reset(self):
        with self._lock:
            windows = self.windows
            initiative_use = self.initiativeUse
            self.windows = {}
            self.initiativeUse = False
            return windows, initiative_use
    def storage_data(self):
        windows,initiative_use = self._get_and_reset()
        if not windows:
            logger.warning("sorted windows is empty")
            return
        db.sqlite.bulk_insert_window_activities(windows)

    def merge_and_storage_data(self):
        self.merge_data()
        self.storage_data()

    def start_sort(self):
        self.schedulerManager.add_minute(self.minute,"merge_data",self.merge_and_storage_data)
        self.schedulerManager.scheduler.start()
    def stop_sort(self):
        self.schedulerManager.scheduler.shutdown()




