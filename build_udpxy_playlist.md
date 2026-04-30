# build_udpxy_playlist.py UDPXY 播放列表生成工具

## 功能概述

用于从组播地址模板文件和 udpxy 服务器列表生成 IPTV 播放列表。支持 txt 和 m3u 两种输出格式，可自动进行服务器测速，支持推送到 Gitee 和 GitHub 仓库。

## 处理流程

### 1. 初始化

```
读取配置参数
    ↓
加载频道分类配置（config/iptv_category.txt）
    ↓
检查 source/multicast/ 目录中的模板文件
```

### 2. 处理每个省份

```
对每个模板文件执行：
    ↓
识别省份（从文件名提取）
    ↓
检查现有文件（可选：验证是否可用，决定是否重新生成）
    ↓
读取模板内容，提取组播靶标（自动识别 rtp/udp/igmp 协议，支持纯 IP 地址格式）
    ↓
获取 udpxy 服务器（从 Quake API 或本地 nodes.txt 文件）
    ↓
对服务器进行测速（可选，按速度排序）
    ↓
解析频道信息，标准化频道名和分类
    ↓
按分类排序，生成播放列表
    ↓
写入 output/{省份名}.txt 和 output/{省份名}.m3u
```

### 3. 推送（可选）

```
读取推送记录（push_records.json）
    ↓
检查文件是否已推送过相同内容
    ↓
├── Gitee 推送（如果配置了 Gitee 令牌）
└── GitHub 推送（如果配置了 GitHub 令牌）
    ↓
更新推送记录
```

## 配置参数

### 数据源配置

```python
DATA_SOURCE = "local"  # 可选："quake" 或 "local"
QUAKE_TOKEN = "..."  # Quake API 令牌（使用 Quake 时需要）
TEMPLATE_DIR = "source/multicast"  # 模板文件目录
LOCAL_NODES_FILE = "nodes.txt"  # 本地节点文件
FORCE_GENERATE = True  # 是否强制生成（跳过现有文件验证）
```

### 服务器测速配置

```python
ENABLE_SERVER_TEST = False  # 是否对服务器进行测速
TEST_MAX_WORKERS = 20  # 并发测速服务器节点数量
GENERATE_MAX_SERVERS = 5  # 生成时使用的服务器数量（按速度取前 N 个）
```

### Gitee 推送配置

```python
GITEE_TOKEN = "..."  # Gitee 私人令牌
GITEE_USER = "..."  # Gitee 用户名
GITEE_REPO = "..."  # Gitee 仓库名
GITEE_BRANCH = "master"  # Gitee 分支名
GITEE_AUTO_PUSH = True  # 是否自动推送到 Gitee
```

### GitHub 推送配置

```python
GITHUB_TOKEN = "..."  # GitHub 个人访问令牌
GITHUB_USER = "..."  # GitHub 用户名
GITHUB_REPO = "..."  # GitHub 仓库名
GITHUB_BRANCH = "main"  # GitHub 分支名
GITHUB_AUTO_PUSH = True  # 是否自动推送到 GitHub
```

## 频道分类配置

### 配置文件格式

config/iptv_category.txt:
```
ID,频道名,分类,别名1|别名2|别名3...
100100,CCTV1,央视,CCTV1|CCTV-1|CCTV综合|CCTV-综合|中央1
100200,CCTV2,央视,CCTV2|CCTV-2|经济频道
100300,CCTV3,央视,CCTV3|CCTV-3|综艺频道
200100,湖南卫视,卫视,湖南卫视|芒果台
```

### 功能

1. **频道名标准化**：将别名统一替换为标准频道名
2. **分类替换**：使用配置文件中的分类替换原有分类
3. **排序控制**：
   - 按配置文件中的分类出现顺序排序
   - 同一分类内按频道 ID 排序
   - 未在配置中的分类放在最后

## 文件格式

### 模板文件格式（source/multicast/）

#### 格式1：2列格式

```
#genre# 央视频道
CCTV1,rtp://239.49.0.1:8000
CCTV2,rtp://239.49.0.2:8000

#genre# 卫视频道
湖南卫视,rtp://239.49.0.3:8000
```

#### 格式2：3列格式（推荐）

```
央视,CCTV1,rtp://239.49.0.1:8000
央视,CCTV2,rtp://239.49.0.2:8000
卫视,湖南卫视,rtp://239.49.0.3:8000
```

#### 格式3：纯 IP 格式（自动添加 rtp://）

```
央视,CCTV1,239.49.0.1:8000
央视,CCTV2,239.49.0.2:8000
卫视,湖南卫视,239.49.0.3:8000
```

### 本地服务器文件格式（nodes.txt）

#### 格式1：3列格式（推荐）

```
# 运营商,省份,服务器地址
电信,江苏,http://192.168.1.1:8080
电信,江苏,http://192.168.1.2:8080
电信,广东,http://192.168.2.1:8080
```

#### 格式2：2列格式（向后兼容）

```
江苏,http://192.168.1.1:8080
江苏,http://192.168.1.2:8080
```

#### 格式3：1列格式

```
http://192.168.1.1:8080
http://192.168.1.2:8080
```

### 输出文件格式

#### TXT 格式（output/江苏电信.txt）

```
更新时间,#genre#
2026/04/28 14:30,https://taoiptv.com/time.mp4

央视,#genre#
CCTV1,http://192.168.1.1:8080/rtp/239.49.0.1:8000
CCTV1,http://192.168.1.2:8080/rtp/239.49.0.1:8000
CCTV2,http://192.168.1.1:8080/rtp/239.49.0.2:8000
CCTV2,http://192.168.1.2:8080/rtp/239.49.0.2:8000

卫视,#genre#
湖南卫视,http://192.168.1.1:8080/rtp/239.49.0.3:8000
湖南卫视,http://192.168.1.2:8080/rtp/239.49.0.3:8000
```

#### M3U 格式（output/江苏电信.m3u）

```
#EXTM3U
#EXTINF:-1 group-title="更新时间",2026/04/28 14:30
https://taoiptv.com/time.mp4

#EXTINF:-1 group-title="央视",CCTV1
http://192.168.1.1:8080/rtp/239.49.0.1:8000
#EXTINF:-1 group-title="央视",CCTV1
http://192.168.1.2:8080/rtp/239.49.0.1:8000

#EXTINF:-1 group-title="央视",CCTV2
http://192.168.1.1:8080/rtp/239.49.0.2:8000
#EXTINF:-1 group-title="央视",CCTV2
http://192.168.1.2:8080/rtp/239.49.0.2:8000

#EXTINF:-1 group-title="卫视",湖南卫视
http://192.168.1.1:8080/rtp/239.49.0.3:8000
#EXTINF:-1 group-title="卫视",湖南卫视
http://192.168.1.2:8080/rtp/239.49.0.3:8000
```

## 目录结构

```
IPTV-udpxy/
├── source/multicast/      # 模板文件目录
│   ├── 江苏电信.txt
│   ├── 广东电信.txt
│   └── 北京电信.txt
├── config/
│   ├── iptv_category.txt  # 频道分类配置
│   └── test_udpxy_config.txt # 测试配置
├── udpxy_servers/
│   └── udpxy_servers_active.txt # 有效服务器
├── output/                # 生成的播放列表目录
│   ├── 江苏电信.txt
│   ├── 江苏电信.m3u
│   ├── 广东电信.txt
│   └── 广东电信.m3u
├── nodes.txt              # udpxy 服务器列表（与 udpxy_servers_active.txt 同步）
├── push_records.json      # 推送记录（避免重复推送）
└── log/                  # 日志目录
```

## 使用方法

```bash
py build_udpxy_playlist.py
```

### 运行示例

```
======================================================================
      UDPXY IPTV源管理工具 - 开始执行
======================================================================

[*] 配置信息:
    数据源: local
    模板目录: source/multicast
    强制生成: True
    本地节点文件: nodes.txt
    Gitee 推送: 已配置
    GitHub 推送: 已配置
    自动推送: 开启

[*] source/multicast/ 目录中发现 3 个模板文件，开始处理...

======================================================================
  [1/3] 正在处理: 江苏电信.txt
======================================================================
[*] 正在从本地文件读取 [江苏] 地区的节点...
[+] 从本地文件中获取到 10 个节点
[*] 去重后共发现 10 个节点
[*] 不进行测速，使用前 5 个服务器（按原始顺序）
[*] 开始生成直播源文件...
[+] 成功加载频道分类配置，共 100 个别名映射，10 个分类
  - [江苏] 更新完成，获取 5 个纯净节点。
  - 生成文件数量: 2 个 (江苏电信.txt, 江苏电信.m3u)

======================================================================
 本地文件生成完成
 处理省份: 3
 成功更新: 3
======================================================================

[*] 准备执行云端同步...
[*] 发现 6 个文件待推送

[*] 开始推送到 Gitee...
[+] 成功！江苏电信.txt 已更新到 Gitee 仓库的 output 目录！
[+] 成功！江苏电信.m3u 已更新到 Gitee 仓库的 output 目录！
[+] 成功！广东电信.txt 已更新到 Gitee 仓库的 output 目录！
[+] 成功！广东电信.m3u 已更新到 Gitee 仓库的 output 目录！
[*] 文件 北京电信.txt 未变化，跳过推送
[*] 文件 北京电信.m3u 未变化，跳过推送

[*] 开始推送到 GitHub...
[+] 成功！江苏电信.txt 已更新到 GitHub 仓库的 output 目录！
[+] 成功！江苏电信.m3u 已更新到 GitHub 仓库的 output 目录！
[+] 成功！广东电信.txt 已更新到 GitHub 仓库的 output 目录！
[+] 成功！广东电信.m3u 已更新到 GitHub 仓库的 output 目录！
[*] 文件 北京电信.txt 未变化，跳过推送
[*] 文件 北京电信.m3u 未变化，跳过推送

======================================================================
 任务完成！
 流程: 读取本地节点 -> 覆盖生成 -> 云端发布
 如有问题，请检查日志输出或查看项目说明文档
======================================================================
```

## 函数说明

| 函数 | 说明 |
|------|------|
| `load_category_config()` | 加载频道分类配置文件 |
| `normalize_channel_name(name, alias_map)` | 标准化频道名 |
| `get_channel_category(name, channel_info)` | 获取频道分类 |
| `extract_province(filename)` | 从文件名提取省份 |
| `check_url(url)` | 检查 URL 是否有效（下载测试） |
| `check_and_clear_existing(txt_file, m3u_file)` | 检查现有文件是否可用 |
| `get_quake_assets(province)` | 从 Quake API 获取节点 |
| `get_local_assets(province)` | 从本地文件获取节点 |
| `txt_to_m3u_format(txt_content)` | 将 txt 内容转换为 m3u 格式 |
| `process_province(template_filename)` | 处理单个省份模板 |
| `push_to_gitee(filename)` | 推送到 Gitee 仓库 |
| `push_to_github(filename)` | 推送到 GitHub 仓库 |
| `get_content_hash(content)` | 计算内容的 MD5 哈希值 |
| `load_push_records()` / `save_push_records()` | 加载/保存推送记录 |
| `update_push_record(filename, content)` | 更新推送记录 |

## 变量说明

| 变量 | 类型 | 说明 |
|------|------|------|
| `DATA_SOURCE` | str | 数据源：quake 或 local |
| `ENABLE_SERVER_TEST` | bool | 是否进行服务器测速 |
| `TEST_MAX_WORKERS` | int | 并发测速线程数 |
| `GENERATE_MAX_SERVERS` | int | 生成时使用的服务器数量 |
| `GITEE_AUTO_PUSH` / `GITHUB_AUTO_PUSH` | bool | 是否自动推送 |
| `channels_data` | list | 频道数据列表，包含分类、频道名、地址等信息 |
| `valid_hosts` | list | 有效的服务器列表（排序后） |

## 特性

1. **多数据源支持**：支持 Quake API 或本地 nodes.txt 文件
2. **智能去重**：按服务器地址去重，避免重复
3. **服务器测速**：可选的并发测速功能，按速度排序
4. **频道标准化**：自动统一频道名和分类
5. **灵活排序**：按配置文件中的分类顺序和频道 ID 排序
6. **双格式输出**：同时生成 txt 和 m3u 两种格式
7. **去重推送**：智能检测文件变化，避免重复推送
8. **双仓库支持**：同时支持推送到 Gitee 和 GitHub
9. **分支配置**：可配置推送到不同的分支
10. **任意组播地址支持**：支持任意 IP 开头的组播地址（225.、233.、239.等）

## 测速逻辑

当 `ENABLE_SERVER_TEST = True` 时：

1. 从模板文件提取组播靶标地址
2. 为每个服务器构建测试 URL：`http://server/rtp/239.49.0.1:8000`
3. 并发测试所有服务器（线程数 = `TEST_MAX_WORKERS`）
4. 检查是否下载了至少 16KB 数据
5. 对有效服务器按耗时从小到大排序
6. 取前 `GENERATE_MAX_SERVERS` 个服务器用于生成

## 推送机制

1. **哈希比较**：计算文件内容的 MD5 哈希值
2. **记录比对**：与 `push_records.json` 中的记录比对
3. **条件推送**：
   - 相同哈希：跳过（避免重复推送）
   - 不同哈希：推送新内容并更新记录
4. **新建/更新区分**：
   - Gitee：检查文件是否存在，存在用 PUT，不存在用 POST
   - GitHub：统一用 PUT（自动处理新建和更新）

## 注意事项

1. **编码问题**：自动尝试 utf-8、gbk、gb2312、ansi 编码读取文件
2. **模板必需**：source/multicast/ 目录需要至少有一个模板文件
3. **服务器配置**：使用本地数据源时，nodes.txt 需要包含对应地区的服务器
4. **推送配置**：推送到仓库前请确保配置了正确的 Token 和用户名
5. **分支选择**：Gitee 默认推送到 master，GitHub 默认推送到 main
6. **分类优先级**：配置文件中的分类按出现顺序排序，未配置的分类放在最后
7. **协议兼容**：同时支持 rtp、udp、igmp 协议，以及纯 IP 格式（自动添加 rtp://）
8. **路径编码**：Gitee/GitHub 推送时自动对中文路径进行 URL 编码

