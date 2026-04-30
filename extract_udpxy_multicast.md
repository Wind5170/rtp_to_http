# extract_udpxy_multicast.py 组播地址提取工具

## 功能概述

用于从多个列表文件中提取频道和组播地址数据，支持 `.txt` 和 `.m3u` 格式，并生成标准化的输出文件。

## 处理流程

### 1. 文件选择

```
弹出文件选择对话框（默认目录: playlists\collected）
    ↓
选择多个文件（.txt 或 .m3u）
    ↓
验证所有文件是否在同一目录下
```

### 2. 地区识别

支持从文件所在目录及上一级目录提取运营商和地区信息
```
优先从文件名提取运营商、地区（如"广东电信.txt"提取"广东-电信"
    ↓
从当前目录名提取（如"广东电信"目录，提取"广东-电信"）
    ↓
从上一级目录名提取（如"广东电信/test/，提取"广东-电信"）
    ↓
返回地区名称（未知则返回"未知"，运营商默认为"电信"

处理模式：
├── 文件名有运营商、地区信息 → 每个文件单独处理，结果存入对应输出文档
└── 文件名无运营商、地区信息 → 合并所有文件，使用目录提取的信息
```

### 3. 数据提取

#### 3.1 TXT 格式处理

```
逐行读取文件
    ↓
识别行类型：
├── #genre# ──→ 分类标记（更新当前分类，可能没有分类）
├── udpxy模式 ──→含（分类，3列型有，2列型没有）、频道名、地址部分： http://udpxy服务器/rtp/组播地址 或 http://udpxy服务器/udp/组播地址，提取: udpxy服务器,（分类，3列型有，2列型没有）、频道名、组播地址
└── 纯组播 ──→ 含（分类，3列型有，2列型没有）、频道名、地址部分：rtp://组播地址 或 udp://组播地址 或 没有rtp://、udp://头的纯组播地址（任意IP开头，提取:（分类，3列型有，2列型没有）、频道名、组播地址
```

#### 3.2 M3U 格式处理

```
读取 #EXTINF 行 ──→ 提取分类、频道名
    ↓
读取下一行 URL ──→ 提取组播地址
    ↓
识别模式：
├── udpxy模式 ──→ 地址部分：http://udpxy服务器/rtp/组播地址 或 http://udpxy服务器/udp/组播地址，提取: udpxy服务器,组播地址
└── 纯组播 ──→ 地址部分：rtp://组播地址 或 udp://组播地址 或 没有rtp://、udp://头的纯组播地址（任意IP开头），提取: 组播地址
```

#### 3.3 模板变量格式

```
支持模板变量模式，如:
CCTV1,http://{{your_udpxy_address}/udp/239.50.201.118:5140

处理方式：
├── 保存频道信息到 channels 字典
└── 模板变量不添加到 servers 集合（不保存到服务器列表）
```

### 4. 数据去重

#### 4.1 数据结构

```python
channels = {multicast_addr: (category, channel_name)}
servers = {server1, server2, ...}
```

#### 4.2 分类更新优先级

| 原有分类 | 新读取分类 | 处理方式 |
|---------|-----------|---------|
| 非"未分类" | "未分类" | 不更新 |
| "未分类" | 非"未分类" | 更新 |
| 非"未分类" | 非"未分类" | 更新为新值 |
| "未分类" | "未分类" | 不更新 |

### 5. 输出文件

#### 5.1 组播地址文件

- **路径**：`multicast_addresses/extracted/{地区}_{运营商}_extracted_multicast_addresses.txt`
- **第一行**：`# {更新时间}`
- **格式**：`{分类},{频道名},{组播地址}`

#### 5.2 服务器文件

- **路径**：`udpxy_servers/extracted/{地区}_{运营商}_extracted_udpxy_servers.txt`
- **第一行**：`# {更新时间}`
- **格式**：每行一个服务器地址（带http://头）

## 文件格式

### 支持的输入格式

#### TXT 格式

```
# genre# 央视频道
CCTV1,http://115.216.161.183:8088/rtp/233.50.201.222:5140
CCTV2,rtp://233.50.201.119:5140
央视,CCTV2,rtp://233.50.201.119:5140
```

或模板格式
```
央视,#genre#
CCTV1,http://{{your_udpxy_address}/rtp/233.50.201.118:5140
CCTV2,http://{{your_udpxy_address}/udp/233.50.201.119:5140
```

#### M3U 格式

```
#EXTM3U
#EXTINF:-1 group-title="央视频道",CCTV1
http://115.216.161.183:8088/rtp/233.50.201.222:5140
#EXTINF:-1 group-title="卫视频道",湖南卫视
rtp://233.50.201.52:5140
#EXTINF:-1 group-title="央视频道",CCTV2
233.50.201.119:5140
```

### 生成的输出格式

```
# 2026/04/28 14:30
央视频道,CCTV1,233.50.201.222:5140
央视频道,CCTV2,233.50.201.119:5140
央视,CCTV2,rtp://233.50.201.119:5140
卫视频道,湖南卫视,233.50.201.52:5140
```

## 目录结构

```
IPTV-udpxy/
├── playlists/
│   ├── collected/          # 输入文件目录
│   │   ├── 安徽电信.txt
│   │   ├── 北京电信.txt
│   │   └── 广东电信/
│   │       ├── 2026.txt
│   │       └── 2026.m3u
│   └── extracted/          # 输出组播地址目录
│       ├── 安徽_电信_extracted_multicast_addresses.txt
│       ├── 北京_电信_extracted_multicast_addresses.txt
│       └── 广东_电信_extracted_multicast_addresses.txt
├── multicast_addresses/
│   └── extracted/          # 输出组播地址目录
│       ├── 安徽_电信_extracted_multicast_addresses.txt
│       ├── 北京_电信_extracted_multicast_addresses.txt
│       └── 广东_电信_extracted_multicast_addresses.txt
└── udpxy_servers/
    └── extracted/          # 输出服务器目录
        ├── 安徽_电信_extracted_udpxy_servers.txt
        ├── 北京_电信_extracted_udpxy_servers.txt
        └── 广东_电信_extracted_udpxy_servers.txt
```

## 使用方法

```bash
py extract_udpxy_multicast.py
```

### 运行示例

#### 示例1：文件名包含地区信息

```
处理文件: J:/GitHub_Project/IPTV/IPTV-udpxy/playlists/collected/江苏电信.txt
提取地区: 江苏, 运营商: 电信
写入组播地址文件: playlists/extracted/江苏_电信_extracted_multicast_addresses.txt
写入服务器文件: udpxy_servers/extracted/江苏_电信_extracted_udpxy_servers.txt
本次读取: 139 个频道, 2 个服务器
新增: 0 个频道, 0 个服务器
```

#### 示例2：文件名无地区信息，从目录提取

```
文件名未包含地区/运营商信息，从目录提取: 广东-电信
合并处理所有文件:
  - J:/GitHub_Project/IPTV/playlists/collected/广东电信/2026.txt
  - J:/GitHub_Project/IPTV/playlists/collected/广东电信/2026.m3u
本次读取: 100 个频道, 3 个服务器
新增: 50 个频道, 1 个服务器
共有数据: 150 个频道, 3 个服务器
```

## 函数说明

| 函数 | 说明 |
|------|------|
| `extract_info(line, current_category)` | 从 txt 格式行提取频道名、服务器、地址 |
| `extract_info_from_m3u(extinf, url)` | 从 m3u 格式提取频道信息 |
| `extract_region(file_path)` | 从文件名或目录名提取地区和运营商 |
| `get_region_isp_for_file(file_path)` | 获取文件的地区和运营商 |
| `normalize_path(path)` | 规范化路径（反斜杠转正斜杠 |
| `process_file(...)` | 处理单个文件，返回提取结果 |
| `select_files()` | 弹出文件选择对话框 |

## 变量说明

| 变量 | 类型 | 说明 |
|------|------|------|
| `channels` | dict | 组播地址字典 {地址: (分类, 频道名)} |
| `servers` | set | udpxy 服务器集合（不含 http:// 前缀） |
| `read_channels` | int | 本次读取的频道数 |
| `read_servers` | int | 本次读取的服务器数 |
| `added_channels` | int | 新增的频道数（相对于已有文件） |
| `added_servers` | int | 新增的服务器数（相对于已有文件） |
| `current_category` | str | 当前分类 |
| `region` | str | 地区名称 |
| `isp` | str | 运营商 |
| `current_time` | str | 当前时间（格式：YYYY/MM/DD HH:MM） |

## 特性

1. **智能去重**：根据组播地址去重，保留最新的分类信息
2. **分类优先级**："未分类"优先级最低，不会覆盖已有的分类
3. **多格式支持**：支持 txt 和 m3u 格式，支持 rtp 和 udp 协议
4. **地区识别**：自动从文件名或目录名识别地区，支持上一级目录
5. **运营商识别**：自动识别电信、移动、联通运营商
6. **追加模式**：读取已有数据，新数据追加而非覆盖
7. **模板变量支持**：支持 {{var} 模板格式，模板变量不添加到服务器列表
8. **读取/新增统计**：显示本次读取数和相对已有文件的新增数
9. **任意组播地址支持**：支持任意IP开头的组播地址（225.开头也支持）

## 支持的输入格式汇总

| 格式 | 示例 | 说明 |
|-----|------|------|
| 1. 2列格式（udpxy模式） | `CCTV1,http://server/rtp/239.1.1.1:8000` | udpxy 服务器模式 |
| 2. 3列格式（udpxy模式） | `央视,CCTV1,http://server/rtp/239.1.1.1:8000` | 带分类的 udpxy 模式 |
| 3. 2列格式（纯组播） | `CCTV1,rtp://239.1.1.1:8000` | 纯组播模式 |
| 4. 3列格式（纯组播） | `央视,CCTV1,rtp://239.1.1.1:8000` | 带分类的纯组播模式 |
| 5. 纯组播地址 | `239.1.1.1:8000` | 无频道名的纯地址 |
| 6. M3U 格式 | M3U playlist | M3U 播放列表 |
| 7. 模板变量格式 | `CCTV1,http://{{your_udpxy_address}/rtp/239.1.1.1:8000` | 模板变量模式 |

## 注意事项

1. **编码问题**：使用 utf-8-sig 编码读取文件，自动处理 BOM 标记
2. **地区识别优先级**：文件名 → 当前目录 → 上一级目录
3. **去重逻辑**：相同的组播地址只保留一个，根据分类优先级更新分类
4. **服务器去重**：读取现有服务器时，自动去除 http:// 前缀保持一致性
5. **模板变量**：模板变量的服务器地址不添加到服务器列表

