import json
import logging
import os
import sqlite3
from typing import List, Dict

import config.config as conf

# --- SQL 定义 ---
# 将所有需要执行的 SQL 语句放在一个多行字符串中
# 使用 "IF NOT EXISTS" 可以确保只有在表或索引不存在时才创建它们
SQL_CREATE_WINDOW_ACTIVITY = """
CREATE TABLE IF NOT EXISTS window_activity (
    -- 主键, 自动增长, 用于唯一标识每条窗口活动记录
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    which_minute Text NOT NULL,
    -- WindowSorted 核心信息
    window_hwnd INTEGER NOT NULL,
    start_time TEXT NOT NULL,  -- 窗口开始时间, 'YYYY-MM-DD HH:MM:SS' 格式
    window_titles TEXT,              -- 存储窗口标题列表的 JSON 字符串, 例如: '["Title 1", "Title 2"]'
    main_window_time REAL DEFAULT 0, -- 担任主窗口的时间 (秒)
    media_use_time REAL DEFAULT 0,   -- 音频使用时间 (秒)
    micro_use_time REAL DEFAULT 0,   -- 麦克风使用时间 (秒)
    camera_use_time REAL DEFAULT 0,  -- 摄像头使用时间 (秒)
    media_share_time REAL DEFAULT 0, -- 音频共享时间 (秒)
    micro_share_time REAL DEFAULT 0, -- 麦克风共享时间 (秒)
    camera_share_time REAL DEFAULT 0, -- 摄像头共享时间 (秒)

    -- 从 KeyBoardInfo 平铺的字段
    keyboard_press_num INTEGER DEFAULT 0,
    keyboard_press_list TEXT,        -- 存储按键统计字典的 JSON 字符串, 例如: '{"a": 10, "Control": 5}'

    -- 从 MouseInfo 平铺的字段
    mouse_scroll_num INTEGER DEFAULT 0,
    mouse_move_num INTEGER DEFAULT 0,
    mouse_left_click_num INTEGER DEFAULT 0,
    mouse_right_click_num INTEGER DEFAULT 0,
    mouse_other_click_num INTEGER DEFAULT 0,

    -- 记录创建时间戳
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS process_snapshots (
    -- 主键, 自动增长
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    which_minute Text NOT NULL,
    -- 外键, 关联到 window_activity 表的 id
    -- ON DELETE CASCADE 表示当主表中的窗口活动记录被删除时, 相关的进程快照也会被自动删除
    activity_id INTEGER NOT NULL,

    -- ProcesSorted 核心信息
    pid INTEGER NOT NULL,
    name TEXT,
    path TEXT,
    username TEXT,
    start_time TEXT,
    statuses TEXT,                  -- 存储进程状态列表的 JSON 字符串, 例如: '["running", "sleeping"]'

    -- 从 MemorySorted 平铺的字段 (平均值)
    avg_memory_percent REAL DEFAULT 0,
    avg_rss REAL DEFAULT 0,
    avg_vms REAL DEFAULT 0,
    avg_peak_wset REAL DEFAULT 0,
    avg_num_page_fault REAL DEFAULT 0,

    -- 从 IOSorted 平铺的字段 (总计)
    total_read_call INTEGER DEFAULT 0,
    total_write_call INTEGER DEFAULT 0,
    total_read_bytes INTEGER DEFAULT 0,
    total_write_bytes INTEGER DEFAULT 0,

    FOREIGN KEY (activity_id) REFERENCES window_activity(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS minute_initiativeUse (
    -- 主键, 自动增长, 用于唯一标识每条窗口活动记录
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    which_minute Text NOT NULL,
    is_initiative_use NOT NULL
);
-- 在 process_snapshots 表的 activity_id 列上创建索引，以加速 JOIN 查询
CREATE INDEX IF NOT EXISTS idx_process_snapshots_activity_minute_id ON process_snapshots (which_minute,activity_id);

-- 在 window_activity 表的 which_minute 列上创建索引，以加速按时间范围的查询
CREATE INDEX IF NOT EXISTS idx_window_activity_which_minute ON window_activity (which_minute);

-- 在 window_activity 表的 start_time 列上创建索引，以加速按时间范围的查询
CREATE INDEX IF NOT EXISTS idx_minute_initiativeUse_which_minute ON minute_initiativeUse (which_minute);
"""


def get_db_connection():
    return sqlite3.connect(db_file_path)
def setup_db_file():


    db_name = config['db']["file_name"]
    # 确保数据库文件存在
    db_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        db_name
    )
    # 文件不存在,创建文件
    if db_path and not os.path.exists(db_path):
        try:
            with open(db_path, 'w') as file:
                pass  # 不写入内容，仅创建文件
            logger.info(f"文件 {db_path} 创建成功")
        except Exception as e:
            logger.error(f"创建文件失败: {e}")

    return db_path
def create_window_activity_table():

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # 使用 executescript 执行包含多个 SQL 语句的脚本
        cursor.executescript(SQL_CREATE_WINDOW_ACTIVITY)

        # 提交事务
        conn.commit()
        logger.info("数据库初始化成功。表和索引已准备就绪。")

    except sqlite3.Error as e:
        logger.error(f"数据库初始化时发生错误: {e}")
    finally:
        # 确保数据库连接被关闭
        if conn:
            conn.close()
def bulk_insert_window_activities(window_dict: Dict):
    """
    高效地批量插入多个 WindowSorted 对象到数据库。
    所有插入操作都在一个事务中完成。

    Args:
        window_dict: 一个包含多个 WindowSorted 对象的列表。
    """
    logger.info(f"准备批量插入 {len(window_dict)} 条窗口活动记录...")
    conn = get_db_connection()
    # 使用 "with conn:" 来自动管理事务。
    # 它会在代码块开始时自动执行 BEGIN，
    # 如果代码成功执行，则在结束时执行 COMMIT，
    # 如果发生异常，则执行 ROLLBACK。
    try:
        with conn:
            cursor = conn.cursor()

            # 遍历每一个要插入的 WindowSorted 对象
            for window_obj in window_dict.values():
                # --- 步骤 1: 插入主表 (window_activity) ---
                # 因为需要获取每个父记录的 lastrowid，所以主表记录仍然需要逐条插入。
                # 但由于它们都在同一个事务中，所以速度依然非常快。

                window_titles_json = json.dumps(window_obj.windowTitles)
                keyboard_list_json = json.dumps(window_obj.keyboardInfo.keyPressList)

                cursor.execute("""
                               INSERT INTO window_activity (which_minute,window_hwnd, start_time, window_titles, main_window_time,
                                                            media_use_time, micro_use_time, camera_use_time,
                                                            media_share_time, micro_share_time, camera_share_time,
                                                            keyboard_press_num, keyboard_press_list,
                                                            mouse_scroll_num, mouse_move_num, mouse_left_click_num,
                                                            mouse_right_click_num, mouse_other_click_num)
                               VALUES (?,?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                               """, (
                                   window_obj.whichMinute,
                                   window_obj.windowHwnd, window_obj.startTime, window_titles_json,
                                   window_obj.mainWindowTime, window_obj.mediaUseTime,
                                   window_obj.microUseTime, window_obj.cameraUseTime,
                                   window_obj.mediaShareTime, window_obj.microShareTime,
                                   window_obj.cameraShareTime,
                                   window_obj.keyboardInfo.keyPressNum, keyboard_list_json,
                                   window_obj.mouseInfo.mouseScrollNum, window_obj.mouseInfo.mouseMoveNum,
                                   window_obj.mouseInfo.mouseLeftClickNum, window_obj.mouseInfo.mouseRightClickNum,
                                   window_obj.mouseInfo.mouseOtherClickNum
                               ))

                activity_id = cursor.lastrowid

                # --- 步骤 2: 准备并批量插入子表 (process_snapshots) ---
                # 这是另一个性能优化点：使用 executemany()

                if not window_obj.processInfos:
                    continue  # 如果没有进程信息，跳过

                processes_to_insert = []
                for pid, process_info in window_obj.processInfos.items():
                    statuses_json = json.dumps(process_info.status)
                    processes_to_insert.append((
                        activity_id, process_info.pid, process_info.name, window_obj.whichMinute, process_info.path,

                        process_info.username, process_info.startTime,statuses_json,
                        process_info.memoryUsage.avgMemoryPercent,process_info.memoryUsage.avgRss,

                        process_info.memoryUsage.avgVms,process_info.memoryUsage.avgPeakWSet,
                        process_info.memoryUsage.avgNumPageFault,process_info.ioUsage.totalRCallNum,
                        process_info.ioUsage.totalWCallNum,

                        process_info.ioUsage.totalRByteNum,process_info.ioUsage.totalWByteNum,

                    ))

                # 使用 executemany 一次性插入所有关联的进程快照
                # 注意：为了简洁，我只写了部分字段，请补全
                cursor.executemany("""
                                   INSERT INTO process_snapshots (
                                        activity_id, pid, name, which_minute,path,
                                        username,start_time,statuses,avg_memory_percent,avg_rss,
                                        avg_vms,avg_peak_wset,avg_num_page_fault,total_read_call,total_write_call,
                                        total_read_bytes,total_write_bytes
                                   )
                                   VALUES (?, ?, ?, ?, ?,
                                           ?, ?, ?, ?, ?, 
                                           ?, ?, ?, ?, ?, 
                                           ?,?)
                                   """, processes_to_insert)

        logger.info("批量插入成功！所有数据已提交。")

    except sqlite3.Error as e:
        # 如果 "with conn" 代码块中出现任何数据库错误，
        # 事务会自动回滚，数据库将保持操作前的状态。
        logger.warning(f"批量插入时发生数据库错误: {e}. 事务已回滚。")
    finally:
        conn.close()
logger = logging.getLogger(__name__)
config = conf.settings
db_file_path = setup_db_file()
create_window_activity_table()


