

"""
data模块采集的信息
collect.py:采集基本信息，后续交由format.py整理
- WindowsData:一个二维切片，一维切片为某一时刻各个窗口以及对应进程状态
- KeyMouseData: 一个数字用于记录键鼠操作数量，一个切片将键鼠操作 对应到对应窗口
"""
import atexit
import logging

import threading
from datetime import datetime

import comtypes
from comtypes import  CoInitialize, CoUninitialize
from pycaw.pycaw import AudioUtilities, IAudioSessionManager2, IAudioSessionControl2
import win32gui
from win32gui import GetForegroundWindow
import win32process
import psutil
from pynput import mouse, keyboard

from data import schedule

"""
按时统计窗口信息
"""
# 进程信息
class ProcessInfo:
    def __init__(self):
        self.pid = None
        self.name = None
        self.path = None
        self.username = None
        self.status = None
        self.cpuUsage = None
        self.startTime = None
        self.memoryUsage = MemUsage()
        self.ioUsage = IOUsage()

    # 返回传入进程id列表 的进程状态列表
    @staticmethod
    def collect_pids_info(pids):
        process_infos = []
        for pid in pids:

            try:
                # 尝试获取进程对象
                ps = psutil.Process(pid)

                process = ps.as_dict(
                    attrs=['pid', 'name', 'create_time', 'exe', 'io_counters', 'memory_info', 'memory_percent',
                           'status', 'username'])
                mem_info = process.get('memory_info')
                io_info = process.get('io_counters')
                process_info = ProcessInfo()
                process_info.pid = process.get('pid')
                process_info.name = process.get('name')
                process_info.path = process.get('exe')
                process_info.startTime = process.get('create_time')
                process_info.status = process.get('status')
                process_info.username = process.get('username')

                # memory_usage
                process_info.memoryUsage.rss = mem_info.rss
                process_info.memoryUsage.vms = mem_info.vms
                process_info.memoryUsage.peakWSet = mem_info.peak_wset
                process_info.memoryUsage.numPageFault = mem_info.num_page_faults
                process_info.memoryUsage.percent = process.get('memory_percent')

                # io_usage
                process_info.ioUsage.RCallNum = io_info.read_count
                process_info.ioUsage.WCallNum = io_info.write_count
                process_info.ioUsage.RByteNum = io_info.read_bytes
                process_info.ioUsage.WByteNum = io_info.write_bytes

                process_infos.append(process_info)

            # 捕获所有可能在进程消失或无权访问时发生的异常
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # 当进程在我们检查它之前就消失了，或者我们没有权限访问它
                # 这是一种完全正常且预期内的情况，不是一个程序错误。
                # 你可以选择静默处理，或者打印一条信息然后继续。
                logging.log(1,f"Process with PID {pid} no longer exists or access is denied. Skipping.")
                # 这里什么都不做，优雅地跳过这个已消失的进程。

            except Exception as e:
                # 捕获任何其他意料之外的错误，方便调试
                logging.log(1,f"An unexpected error occurred while processing PID {pid}: {e}")

        return process_infos





    @staticmethod
    def use_audio_process(capture=False):
        """
        获取所有正在使用音频的会话。
        :param capture: False=播放 (Render), True=录制 (Capture/Microphone)
        :return: 正在使用音频的进程PID列表
        """
        active_pids = set()
        active_ppids = set()
        CoInitialize()
        atexit.register(CoUninitialize)
        # devices = AudioUtilities.GetSpeakers() # 获取默认播放设备
        # 如果要检查麦克风，请使用 GetMicrophone()
        if capture:
            devices = AudioUtilities.GetMicrophone()
        else:
            devices = AudioUtilities.GetSpeakers()

        if not devices:

            return list(active_pids)

        # 激活设备
        interface = devices.Activate(IAudioSessionManager2._iid_, comtypes.CLSCTX_ALL, None)
        session_manager = interface.QueryInterface(IAudioSessionManager2)

        # 枚举所有会话
        session_enumerator = session_manager.GetSessionEnumerator()
        count = session_enumerator.GetCount()

        for i in range(count):
            session = session_enumerator.GetSession(i)
            if session:
                # 获取会话的控制器
                session_control = session.QueryInterface(IAudioSessionControl2)

                # 检查会话状态是否为活动（正在播放/录制）
                # AudioSessionStateActive = 1
                if session_control.GetState() == 1:
                    # 获取该会话所属的进程ID
                    pid = session_control.GetProcessId()
                    if pid != 0:  # 排除系统声音等没有明确PID的会话
                        active_pids.add(pid)
                        ppid = psutil.Process(pid).ppid()
                        if ppid != 0:
                            active_ppids.add(ppid)

        return active_pids, active_ppids
class MemUsage:
    """
    记录程序的内存使用，单位为byte
    """
    def __init__(self):
        self.memoryPercent = 0
        self.rss = 0
        self.vms = 0
        self.peakWSet = 0
        self.numPageFault = 0
class IOUsage:
    def __init__(self):
        self.RCallNum = 0
        self.WCallNum = 0
        self.RByteNum = 0
        self.WByteNum = 0
# 单个窗口信息
class WindowInfo:
    def __init__(self,window_id,window_title,pids):
        # 窗口信息
        self.isMainWindow = False
        self.windowId = window_id
        self.windowTitle = window_title
        self.pids = pids
        self.startTime = None
        self.processInfos= []
        self.whichTime = None
        # # 键盘鼠标
        # self.keyBoardInfo= KeyBoardInfo()
        # self.mouseInfo= MouseInfo()
        # 音频,麦克风,摄像头
        self.isUseMedia = False
        self.isUseMicroPhone = False
        self.isUseCamera = False

        self.isShareMedia = False
        self.isShareMicroPhone = False
        self.isShareCamera = False
# 汇总信息
class WindowsData:
    def __init__(self,second):
        self._lock = threading.Lock()
        self.window_infos = []
        self.schedulerManager = schedule.SchedulerManager()
        if type(second) != int or second <= 0:
            logging.log(1, "your param is uncorrected.")
            return
        if second < 5:
            logging.log(1, "second must bigger than 10.")
            second = 5
        self.second = second
    def update_window_infos(self,window_info):
        with self._lock:
            self.window_infos.append(window_info)

    # 获取全部的窗口pwnd
    @staticmethod
    def get_all_windows():
        """获取所有可见且有标题的窗口"""
        hwnd_list = []

        # EnumWindows函数需要一个回调函数作为参数
        # 这个回调函数被调用时，会传入两个参数：窗口句柄(hwnd)和自定义参数(lParam)
        def callback(hwnd, lParam):
            # IsWindowVisible判断窗口是否可见
            # GetWindowText获取窗口标题
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                # 将窗口句柄和标题以元组形式添加到列表中
                hwnd_list.append((hwnd, win32gui.GetWindowText(hwnd)))
            return True  # 返回True以继续枚举下一个窗口

        # 调用EnumWindows，传入回调函数和自定义参数（这里我们不需要，所以是None）
        win32gui.EnumWindows(callback, None)
        return hwnd_list
    def collect_window(self):
        """
        往window_infos添加当前窗口快照信息.
        """
        hwnd_list = WindowsData.get_all_windows()
        main_window_id = GetForegroundWindow()
        windows = []
        collect_time = datetime.now()
        micro_active_pids, micro_active_ppids = ProcessInfo.use_audio_process(True)
        media_active_pids, media_active_ppids = ProcessInfo.use_audio_process(False)
        # for process in psutil.process_iter(
        #         ['pid', 'name', 'exe', 'cpu_percent', 'memory_info', 'io_counters', 'create_time']):
        #     all_process.append(process)

        for hwnd, win_title in hwnd_list:
            # 新增window在每分记录信息中
            pids = win32process.GetWindowThreadProcessId(hwnd)
            window = WindowInfo(hwnd, win_title, pids)
            if window.windowId == main_window_id:
                window.isMainWindow = True
            window.whichTime = collect_time
            # window.processInfos = ProcessInfoProcessInfo.collect_process_info(pids, all_process)
            window.processInfos = ProcessInfo.collect_pids_info(pids)
            # 赋值startTime到window
            if len(window.processInfos) != 0:
                window.startTime = window.processInfos[0].startTime
            # 收集音频组件信息
            if micro_active_pids.intersection(pids):
                window.isUseMicroPhone = True
            if media_active_pids.intersection(pids):
                window.isUseMedia = True
            if micro_active_ppids.intersection(pids):
                window.isShareMicroPhone = True
            if media_active_ppids.intersection(pids):
                window.isShareMedia = True
            windows.append(window)
        self.update_window_infos(windows)
    def get_and_reset(self):
        with self._lock:
            window_infos = self.window_infos
            self.window_infos = []
        return window_infos
    def start_collect(self):

        self.schedulerManager.add_second(self.second, "window_collect", self.collect_window)
        if not self.schedulerManager.scheduler.running:
            self.schedulerManager.scheduler.start()
    def stop_collect(self):
        if self.schedulerManager.scheduler.running:
            self.schedulerManager.scheduler.shutdown()



"""
实时统计键鼠信息
"""
class KeyBoardInfo:
    def __init__(self):
        self.keyPressNum = 0
        self.keyPressList = {}
class MouseInfo:
    def __init__(self):
        self.mouseScrollNum = 0
        self.mouseMoveNum = 0
        self.mouseLeftClickNum = 0
        self.mouseRightClickNum = 0
        self.mouseOtherClickNum = 0
class KeyMouseInfo:
    def __init__(self,window_id):
        self.lock = threading.Lock()
        self.keyboardInfo = KeyBoardInfo()
        self.mouseInfo = MouseInfo()
        self.activeWindowId = window_id

    def update_keyboard(self, key):
        with self.lock:
            self.keyboardInfo.keyPressNum += 1
            key_str = str(key)
            self.keyboardInfo.keyPressList[key_str] = self.keyboardInfo.keyPressList.get(key_str, 0) + 1


    def update_mouse_move(self):
        with self.lock:
            self.mouseInfo.mouseMoveNum += 1


    def update_mouse_scroll(self):
        with self.lock:
            self.mouseInfo.mouseScrollNum += 1
    def update_mouse_left_click(self):
        with self.lock:
            self.mouseInfo.mouseLeftClickNum += 1



    def update_mouse_right_click(self):
        with self.lock:
            self.mouseInfo.mouseRightClickNum += 1


    def update_mouse_other_click(self):
        with self.lock:
            self.mouseInfo.mouseOtherClickNum += 1


    def reset_and_get_data(self):
        """
        原子操作：返回当前数据并重置计数器。
        这是关键，确保数据不会被重复计算或丢失。
        """
        with self.lock:
            # 复制当前数据
            kb_data = self.keyboardInfo
            mouse_data = self.mouseInfo
            window_id = self.activeWindowId

            # 重置
            self.keyboardInfo = KeyBoardInfo()
            self.mouseInfo = MouseInfo()
            self.last_active_window_id = -1

            return kb_data, mouse_data, window_id
class KeyMouseData:
    def __init__(self):
        self.lock = threading.Lock()
        self.windowsActivity = {}
        self.activityCounters = 0
        self.mouseListener = mouse.Listener(
            on_move=self.mouse_on_move,
            on_click=self.mouse_on_click,
            on_scroll=self.mouse_on_scroll)
        self.keyboardListener = keyboard.Listener(
            on_press=self.key_on_press)
    def collect_events(self):
        """
        启动监听器
        """
        if not self.keyboardListener.running:
            self.keyboardListener.start()
        if not self.mouseListener.running:
            self.mouseListener.start()

    def get_and_reset(self):
        with self.lock:
            windows_activity = self.windowsActivity
            activity_counters = self.activityCounters
            self.windowsActivity = {}
            self.activityCounters = 0
        return windows_activity, activity_counters
    def stop_collect(self):
        if self.mouseListener.running:
            self.mouseListener.stop()
        if self.keyboardListener.running:
            self.keyboardListener.stop()
    # pynput 对应反应函数
    def key_on_press(self,key):
        main_window_hwnd = GetForegroundWindow()
        with self.lock:
            self.activityCounters += 1
        self.windowsActivity.setdefault(main_window_hwnd, KeyMouseInfo(main_window_hwnd)).update_keyboard(
            key)

    def mouse_on_move(self,x, y):
        main_window_hwnd = GetForegroundWindow()
        with self.lock:
            self.activityCounters += 1
            self.windowsActivity.setdefault(main_window_hwnd, KeyMouseInfo(main_window_hwnd)).update_mouse_move()

    def mouse_on_click(self,x, y, button, pressed):
        if pressed:
            main_window_hwnd = GetForegroundWindow()
            with self.lock:
                self.activityCounters += 1
            if button == mouse.Button.left:
                self.windowsActivity.setdefault(main_window_hwnd,
                                                KeyMouseInfo(main_window_hwnd)).update_mouse_left_click()
            elif button == mouse.Button.right:
                self.windowsActivity.setdefault(main_window_hwnd,
                                                KeyMouseInfo(main_window_hwnd)).update_mouse_right_click()
            else:
                self.windowsActivity.setdefault(main_window_hwnd,
                                                KeyMouseInfo(main_window_hwnd)).update_mouse_other_click()

    def mouse_on_scroll(self,x, y, dx, dy):
        main_window_hwnd = GetForegroundWindow()
        self.windowsActivity.setdefault(main_window_hwnd,
                                        KeyMouseInfo(main_window_hwnd)).update_mouse_scroll()

























