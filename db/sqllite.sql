CREATE TABLE IF NOT EXISTS window_activity (
    -- 主键, 自动增长, 用于唯一标识每条窗口活动记录
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    which_minute TimeStamp NOT NULL
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
    memory_stats_count INTEGER DEFAULT 0,

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
    which_minute TimeStamp NOT NULL,
    is_initiactiveUse NOT NULL,
)
-- 在 process_snapshots 表的 activity_id 列上创建索引，以加速 JOIN 查询
CREATE INDEX IF NOT EXISTS idx_process_snapshots_activity_id ON process_snapshots (activity_id);

-- 在 window_activity 表的 which_minute 列上创建索引，以加速按时间范围的查询
CREATE INDEX IF NOT EXISTS idx_window_activity_which_minute ON window_activity (which_minute);

-- 在 window_activity 表的 start_time 列上创建索引，以加速按时间范围的查询
CREATE INDEX IF NOT EXISTS idx_minute_initiativeUse_which_minute ON minute_initiativeUse (which_minute);