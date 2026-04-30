# UDPXY IPTV源管理工具

## 项目简介

这是一个用于管理和更新IPTV源的工具，主要功能包括：

- 从Quake API获取指定省份的udpxy服务节点
- 深度测试节点的有效性（16KB深度测流验证）
- 根据模板文件生成新的IPTV源文件（.txt和.m3u格式）
- 将生成的文件自动推送到Gitee和GitHub仓库

## 目录结构

```
udpxy/
├── config/                 # 配置文件目录
│   └── test_udpxy_config.txt  # 测试配置文件
├── log/                    # 日志文件目录
├── multicast_addresses/    # 组播地址相关文件
│   ├── collected/          # 收集的组播地址
│   ├── extracted/          # 提取汇总的组播地址
│   ├── curated/            # 精选的有效组播地址（测速）
│   ├── active/             # 当前使用的组播地址（生成播放列表用）
│   └── test/               # 测试文件
├── output/                 # 输出播放列表文件目录
├── playlists/              # 播放列表集合
│   ├── collected/          # 收集的播放列表
│   ├── extracted/          # 提取汇总的播放列表
│   └── output/             # 输出播放列表文件目录（备用）
├── udpxy_servers/          # udpxy服务器列表目录
│   ├── collected/          # 收集的服务器列表文件
│   ├── extracted/          # 提取的服务器数据
│   ├── udpxy_servers_active.txt   # 有效服务器汇总（3列格式）
│   └── udpxy_servers_history.txt  # 测试历史记录（5列格式）
├── build_udpxy_playlist.py # 主脚本：生成IPTV播放列表
├── udpxy_health_check.py   # udpxy服务器健康检查
├── multicast_health_check.py # 组播地址健康检查
├── extract_udpxy_multicast.py # 提取udpxy服务器和组播地址
├── generate_multicast.py   # 生成组播地址文件
├── nodes.txt               # 服务器节点文件（3列格式）
├── push_records.json       # 推送记录文件
└── README.md               # 本文档
```

## 环境要求

- Python 3.6+
- 依赖库：requests

## 配置说明

在`build_udpxy_playlist.py`文件的配置区域，需要填写以下信息：

```python
# 1. 数据源配置
DATA_SOURCE = "local"  # 可选值: "quake" (使用Quake API) 或 "local" (使用本地文件)
QUAKE_TOKEN = "" # 你的 Quake Token
TEMPLATE_DIR = "multicast_addresses/active"  # 母版文件夹名称
LOCAL_NODES_FILE = "nodes.txt"              # 本地节点文件名称
FORCE_GENERATE = False                      # 是否强制生成

# 2. Gitee 推送配置 (填入你的信息)
GITEE_TOKEN = "your_gitee_token"            # Gitee 私人令牌
GITEE_USER = "your_gitee_username"          # Gitee 用户名
GITEE_REPO = "your_repo_name"               # Gitee 仓库名称
GITEE_AUTO_PUSH = False                     # 是否自动推送到Gitee

# 3. GitHub 推送配置 (填入你的信息)
GITHUB_TOKEN = "your_github_token"          # GitHub 私人令牌
GITHUB_USER = "your_github_username"        # GitHub 用户名  
GITHUB_REPO = "your_repo_name"              # GitHub 仓库名称
GITHUB_AUTO_PUSH = False                    # 是否自动推送到GitHub
```

### 数据源选择

- `DATA_SOURCE = "quake"`：使用360 Quake API获取节点信息，需要有效的Quake Token
- `DATA_SOURCE = "local"`：使用本地文件获取节点信息，无需Quake Token

## 核心脚本说明

### 1. build_udpxy_playlist.py (主脚本)

**功能**：根据模板文件和节点信息生成IPTV播放列表

**配置参数**：
- `DATA_SOURCE`: 数据源（`quake` 或 `local`）
- `TEMPLATE_DIR`: 母版模板目录（`multicast_addresses/active`）
- `FORCE_GENERATE`: 是否强制生成
- `ENABLE_SERVER_TEST`: 是否对服务器测速

**输出文件**：
- `output/xxx.txt` - 各省份直播源文本格式
- `output/xxx.m3u` - 各省份直播源 M3U 格式
- `push_records.json` - 推送记录文件（记录文件内容哈希）

---

### 2. udpxy_health_check.py

**功能**：对udpxy服务器进行健康检查

**支持的文件格式**：
1. 5列格式：运营商,省份,城市,服务器地址,标签
2. 4列格式：运营商,省份,城市,服务器地址
3. 3列格式：省份,城市,服务器地址（运营商由文件名/目录名识别）
4. 2列格式：省份,服务器地址（运营商由文件名/目录名识别）

**输出文件**：
- `xxx_health_checked.txt` - 各文件测试结果（原文件同目录）
- `udpxy_servers/udpxy_servers_active.txt` - 有效服务器汇总（3列格式）
- `udpxy_servers/udpxy_servers_history.txt` - 测试历史记录（5列格式）
- `nodes.txt` - 服务器节点文件（3列格式，根目录）

---

### 3. multicast_health_check.py

**功能**：对组播地址进行健康检查

**支持的输入格式**：
- 单列：组播地址（如 `239.49.1.60:6000`）
- 2列：频道名,组播地址
- 3列：分类,频道名,组播地址

**输出文件**：
- `xxx_health_checked.txt` - 测试结果文件（原文件同目录）
- `multicast_addresses/curated/地区_运营商_valid_multicast.txt` - 有效组播地址（去重追加）

---

### 4. extract_udpxy_multicast.py

**功能**：从udpxy链接中提取组播地址

**支持的链接格式**：
- `频道名,http://udpxy服务器/rtp/组播地址:端口`
- `频道名,http://udpxy服务器/udp/组播地址:端口`
- `频道名,rtp://组播地址:端口`
- `分类,频道名,组播地址`

**输出文件**：
- `multicast_addresses/extracted/地区_运营商_extracted_multicast_addresses.txt` - 提取的组播地址
- `xxx_health_checked.txt` - 健康检查结果文件（同目录）

---

### 5. generate_multicast.py

**功能**：生成组播地址文件

**输入文件**：
- `source/channel_list.txt` - 频道列表（格式：分类,频道名称,分辨率,状态,组播地址）

**输出文件**：
- `multicast_addresses/collected/multicast+日期.txt` - 生成的组播地址文件

---

## 数据文件说明

### nodes.txt

**格式**：3列（运营商,省份,服务器地址）

**示例**：
```
# 本地节点文件格式：运营商,省份,服务器地址
电信,北京,example1.com:8080
电信,北京,example2.com:8081
移动,江苏,example3.com:8080
联通,上海,example4.com:8081
```

### test_udpxy_config.txt

**格式**：4列（运营商,省份,频道名,组播地址）

**示例**：
```
电信,江苏,江苏城市,239.49.8.107:8000
电信,上海,东方卫视,239.49.1.100:8000
移动,广东,广东卫视,239.77.0.93:5146
```

## 使用流程

1. **收集服务器节点**：
   - 使用 udpxy_health_check.py 检查服务器健康状态
   - 结果保存到 udpxy_servers_active.txt 和 nodes.txt

2. **准备组播地址模板**：
   - 使用 multicast_health_check.py 检查组播地址
   - 有效地址保存到 multicast_addresses/active/ 目录

3. **生成播放列表**：
   - 运行 build_udpxy_playlist.py
   - 生成各省份的 .txt 和 .m3u 文件

4. **推送至云端**（可选）：
   - 自动推送到 Gitee 和 GitHub 仓库
   - 自动跳过已推送过的相同内容

## 日志记录

日志文件保存在 `log/` 目录下，文件名格式为：
- `log/build_udpxy_playlist_日期时间.log`
- `log/udpxy_health_check_日期时间.log`
- `log/multicast_health_check_日期时间.log`

## 注意事项

1. **依赖安装**：
   ```bash
   pip install requests
   ```

2. **Token 安全**：
   - 请勿将包含 Token 的文件提交到版本控制系统
   - 建议使用环境变量或配置文件管理敏感信息

3. **推送记录**：
   - `push_records.json` 记录已推送文件的内容哈希
   - 相同内容会自动跳过推送，避免重复

4. **文件格式**：
   - 所有文件均使用 UTF-8 编码
   - 确保模板文件格式正确，否则可能导致生成失败