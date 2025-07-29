import timeit
from datetime import time
from time import sleep

# 收集系统信息
# [1.用户进程信息,2.用户前置窗口 3.调用音频组件进程 4.调用麦克风程序 5.键盘,鼠标活动与否]
# 每分钟收集

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

class SchedulerManager:
    def __init__(self):
        # 任务存储类型
        job_stores = {
            'default': MemoryJobStore()
        }

        # 执行器,线程池执行
        executors = {
            'default': ThreadPoolExecutor(10),
        }

        # 调度器
        scheduler = BackgroundScheduler(

            jobstores=job_stores,
            executors=executors,
            timezone='Asia/Shanghai'
        )
        self.scheduler = scheduler

    def add_cron(self,cron_string,function_name,function_def):

        # 触发器
        cron_char_list = cron_string.split(',')

        if len(cron_char_list) != 5:
            print("Cron is wrong.")
            return
        trigger = CronTrigger(second=cron_char_list[0], minute=cron_char_list[1], hour=cron_char_list[2],
                              day=cron_char_list[3], month=cron_char_list[4])



        self.scheduler.add_job(
            trigger=trigger,
            func=function_def,
            id=function_name,
        )

    def add_second(self,second,function_name,function_def):

        if type(second) != int:
            return
        self.scheduler.add_job(func=function_def,id=function_name,trigger='interval',seconds=second)

    def add_minute(self,minute,function_name,function_def):
        if type(minute) != int:
            return
        self.scheduler.add_job(func=function_def,id=function_name,trigger='interval',minutes=minute)