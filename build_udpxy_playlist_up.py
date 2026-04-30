import requests
import os
import re
import sys
import base64
import time
import datetime
import urllib.parse  # 新增：用于中文路径的安全编码
from concurrent.futures import ThreadPoolExecutor

# ================= 配置区域 =================
# 1. 数据源配置
DATA_SOURCE = "local"  # 可选值: "quake" (使用Quake API) 或 "local" (使用本地文件)
QUAKE_TOKEN = "your_QUAKE_TOKEN" # 你的 Quake Token
TEMPLATE_DIR = "multicast_addresses/active"                      # 母版文件夹名称
LOCAL_NODES_FILE = "nodes.txt"                        # 本地节点文件名称
FORCE_GENERATE = True                                # 是否强制生成（跳过现有文件有效性检查）

# 2. 服务器测速配置
ENABLE_SERVER_TEST = False  # 是否对服务器进行测速，False则按原始顺序使用服务器
TEST_MAX_WORKERS = 20  # 并发测速服务器节点数量，默认最大20
GENERATE_MAX_SERVERS = 5  # 生成时使用服务器数量，默认最大5

# 3. Gitee 推送配置 (填入你的信息)
GITEE_TOKEN = "your_GITEE_TOKEN"              # Gitee 私人令牌
GITEE_USER = "your_GITEE_USER"                     # Gitee 个人主页URL里的英文用户名
GITEE_REPO = "your_GITEE_REPO"                            # Gitee 仓库名称
GITEE_BRANCH = "master"                          # Gitee 分支名称
GITEE_AUTO_PUSH = True                         # 是否自动推送至Gitee，False则跳过推送

# 4. GitHub 推送配置 (填入你的信息)
GITHUB_TOKEN = "your_GITHUB_TOKEN"                                    # GitHub 私人令牌 (Personal Access Token)
GITHUB_USER = "your_GITHUB_USER"                                    # GitHub 用户名
GITHUB_REPO = "your_GITHUB_REPO"                                    # GitHub 仓库名称
GITHUB_BRANCH = "main"                              # 分支名称
GITHUB_AUTO_PUSH = True                            # 是否自动推送至GitHub，False则跳过推送

# 5. 推送记录配置
PUSH_RECORDS_FILE = "push_records.json"             # 推送记录文件路径

# 6. 频道分类配置
CATEGORY_CONFIG_FILE = "config/iptv_category.txt"    # 频道分类配置文件
# ============================================

import hashlib

def get_content_hash(content):
    """计算内容的MD5哈希值"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def load_push_records():
    """加载推送记录"""
    if os.path.exists(PUSH_RECORDS_FILE):
        try:
            with open(PUSH_RECORDS_FILE, 'r', encoding='utf-8') as f:
                import json
                return json.load(f)
        except:
            return {}
    return {}

def save_push_records(records):
    """保存推送记录"""
    try:
        import json
        with open(PUSH_RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False

def check_push_record(filename, content):
    """检查是否已推送过相同内容"""
    records = load_push_records()
    content_hash = get_content_hash(content)
    
    if filename in records and records[filename] == content_hash:
        return True  # 已推送过相同内容
    return False  # 未推送过或内容已更新

def update_push_record(filename, content):
    """更新推送记录"""
    records = load_push_records()
    content_hash = get_content_hash(content)
    records[filename] = content_hash
    save_push_records(records)

# 中国省份全称及简称对照表，用于智能嗅探
PROVINCES = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", 
             "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", 
             "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", 
             "甘肃", "青海", "宁夏", "新疆"]

# 运营商列表
ISPS = ["电信", "移动", "联通"]

def detect_isp(file_name, dir_name=""):
    """从文件名或目录名识别运营商"""
    if "移动" in file_name or "移动" in dir_name:
        return "移动"
    elif "联通" in file_name or "联通" in dir_name:
        return "联通"
    return "电信"

def get_root_domain(domain):
    """提取根域名，防 DDNS 假去重"""
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain): return domain
    parts = domain.split('.')
    if len(parts) >= 3:
        if parts[-2] in ['com', 'net', 'org', 'gov', 'edu', 'gx'] or len(parts[-2]) <= 2:
            return ".".join(parts[-3:])
        else: return ".".join(parts[-2:])
    return domain

def load_category_config():
    """加载频道分类配置文件"""
    alias_to_channel = {}  # 频道别名 -> 标准化频道名
    channel_info = {}      # 标准化频道名 -> (分类, id)
    category_order = []    # 分类顺序（按出现顺序）
    
    if not os.path.exists(CATEGORY_CONFIG_FILE):
        print(f"[-] 频道分类配置文件不存在: {CATEGORY_CONFIG_FILE}")
        return alias_to_channel, channel_info, category_order
    
    try:
        with open(CATEGORY_CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(',', 3)
                if len(parts) >= 3:
                    channel_id = parts[0].strip()
                    channel_name = parts[1].strip()
                    category = parts[2].strip()
                    aliases = parts[3].strip() if len(parts) >= 4 else ''
                    
                    # 存储频道信息
                    channel_info[channel_name] = (category, channel_id)
                    
                    # 记录分类顺序
                    if category and category not in category_order:
                        category_order.append(category)
                    
                    # 添加标准化频道名本身作为别名
                    alias_to_channel[channel_name] = channel_name
                    
                    # 添加其他别名
                    if aliases:
                        for alias in aliases.split('|'):
                            alias = alias.strip()
                            if alias:
                                alias_to_channel[alias] = channel_name
        
        print(f"[+] 成功加载频道分类配置，共 {len(alias_to_channel)} 个别名映射，{len(category_order)} 个分类")
    except Exception as e:
        print(f"[-] 加载频道分类配置出错: {e}")
    
    return alias_to_channel, channel_info, category_order

def normalize_channel_name(channel_name, alias_to_channel):
    """根据别名映射标准化频道名"""
    if channel_name in alias_to_channel:
        return alias_to_channel[channel_name]
    return channel_name

def get_channel_category(channel_name, channel_info):
    """获取频道分类"""
    normalized_name = normalize_channel_name(channel_name, {})
    if normalized_name in channel_info:
        return channel_info[normalized_name][0]
    return "未分类"

def extract_province(filename):
    """智能识别省份"""
    for p in PROVINCES:
        if p in filename: return p
    return None

def check_url(url):
    """16KB 深度硬核测流验证 (拒绝假存活)"""
    try:
        start_time = time.time()
        with requests.get(url, stream=True, timeout=(3, 5)) as resp:
            if resp.status_code == 200:
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk: downloaded += len(chunk)
                    if downloaded >= 16384:
                        end_time = time.time()
                        speed = end_time - start_time
                        print(f"  [√ 有效] {url} (耗时: {speed:.2f}s)")
                        return url, speed
                end_time = time.time()
                print(f"  [× 无效] {url} (下载不足16KB)")
                return None, 0
    except Exception: pass
    return None, 0

def check_and_clear_existing(txt_file, m3u_file):
    """检测当前目录文件，失效则雷霆清空"""
    if not os.path.exists(txt_file): return False
    urls = []
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r'https?://[^\s,]+', line)
                if match: urls.append(match.group())
                if len(urls) >= 2: break
    except Exception: return False

    if urls:
        print(f"[*] 测试现有文件 [{txt_file}] ...")
        for url in urls:
            res_url, _ = check_url(url)
            if res_url:
                print(f"[!] 结论: 源依然坚挺，跳过本省份。")
                return True
    
    print(f"[*] 结论: 源已失效，正在清空旧文件...")
    for file in [txt_file, m3u_file]:
        with open(file, 'w', encoding='utf-8') as f: f.write("") 
    return False

def get_quake_assets(province, isp=""):
    """针对指定省份请求节点"""
    region = f"{province}-{isp}" if isp else province
    
    url = "https://quake.360.net/api/v3/search/quake_service"
    query_str = f'app:"udpxy" AND is_domain:true AND province:"{province}"'
    headers = {"X-QuakeToken": QUAKE_TOKEN, "Content-Type": "application/json"}
    payload = {"query": query_str, "start": 0, "size": 20, "is_domain": True}

    print(f"[*] 正在从 Quake API 请求 [{region}] 地区的新节点...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                assets = data.get('data', [])
                print(f"[+] 成功获取 {len(assets)} 个节点")
                return assets
            else:
                print(f"[-] Quake API 返回错误: {data.get('message', '未知错误')}")
        else:
            print(f"[-] Quake API 请求失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"[-] Quake API 请求异常: {e}")
    return []

def clean_server_address(server):
    """清理服务器地址，移除 http:// 或 https:// 前缀"""
    server = server.strip()
    if server.startswith('http://'):
        server = server[7:]
    elif server.startswith('https://'):
        server = server[8:]
    return server

def get_local_assets(province, isp=""):
    """从本地文件读取节点信息，支持3列格式：运营商,省份,服务器地址"""
    region = f"{province}-{isp}" if isp else province
    print(f"[*] 正在从本地文件读取 [{region}] 地区的节点...")
    assets = []
    
    if not os.path.exists(LOCAL_NODES_FILE):
        print(f"[-] 本地节点文件 [{LOCAL_NODES_FILE}] 不存在，创建示例文件...")
        # 创建示例文件（3列格式）
        sample_content = "# 本地节点文件格式：运营商,省份,服务器地址\n# 例如：电信,江苏,example.com:8080\n\n电信,北京,example1.com:8080\n电信,北京,example2.com:8081\n电信,上海,example3.com:8080\n电信,上海,example4.com:8081"
        with open(LOCAL_NODES_FILE, 'w', encoding='utf-8') as f:
            f.write(sample_content)
        print(f"[+] 示例文件已创建，请在 [{LOCAL_NODES_FILE}] 中添加节点信息")
        return assets
    
    try:
        with open(LOCAL_NODES_FILE, 'r', encoding='utf-8') as f:
            line_count = 0
            valid_count = 0
            for line in f:
                line_count += 1
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 解析3列格式：运营商,省份,服务器地址
                parts = line.split(',')
                if len(parts) >= 3:
                    # 3列格式：运营商,省份,服务器地址
                    isp = parts[0].strip()
                    node_province = parts[1].strip()
                    server = parts[2].strip()
                    
                    # 清理服务器地址，移除 http:// 前缀
                    server = clean_server_address(server)
                    
                    # 只处理当前省份的节点
                    if node_province == province:
                        if ':' in server:
                            domain, port = server.split(':', 1)
                            try:
                                port = int(port)
                                assets.append({
                                    'domain': domain,
                                    'port': port,
                                    'isp': isp
                                })
                                valid_count += 1
                            except ValueError:
                                print(f"[-] 第 {line_count} 行端口格式错误: {line}")
                elif len(parts) >= 2:
                    # 2列格式：省份,服务器地址（向后兼容）
                    node_province = parts[0].strip()
                    server = parts[1].strip()
                    
                    # 清理服务器地址，移除 http:// 前缀
                    server = clean_server_address(server)
                    
                    if node_province == province and ':' in server:
                        domain, port = server.split(':', 1)
                        try:
                            port = int(port)
                            assets.append({
                                'domain': domain,
                                'port': port,
                                'isp': None
                            })
                            valid_count += 1
                        except ValueError:
                            print(f"[-] 第 {line_count} 行端口格式错误: {line}")
                elif ':' in line:
                    # 单列格式（向后兼容）
                    server = clean_server_address(line)
                    domain, port = server.split(':', 1)
                    try:
                        port = int(port)
                        assets.append({
                            'domain': domain,
                            'port': port,
                            'isp': None
                        })
                        valid_count += 1
                    except ValueError:
                        print(f"[-] 第 {line_count} 行端口格式错误: {line}")
    except Exception as e:
        print(f"[-] 读取本地节点文件出错: {e}")
    
    print(f"[+] 从本地文件中获取到 {len(assets)} 个节点")
    return assets

def txt_to_m3u_format(txt_content):
    """智能转换 M3U 分组格式"""
    m3u_lines = []
    current_group = "未分类"
    for line in txt_content.splitlines():
        line = line.strip()
        if not line: continue
        if '#genre#' in line:
            current_group = line.split(',')[0].strip()
        elif ',' in line:
            name, url = [p.strip() for p in line.split(',', 1)]
            m3u_lines.append(f'#EXTINF:-1 group-title="{current_group}",{name}\n{url}')
    return "\n".join(m3u_lines)

def txt_line_to_m3u(line):
    """将单行 txt 转换为 m3u 条目"""
    line = line.strip()
    if not line or '#genre#' in line:
        return None
    if ',' in line:
        name, url = [p.strip() for p in line.split(',', 1)]
        return f'#EXTINF:-1 group-title="未分类",{name}\n{url}'
    return None

def process_province(template_filename):
    """单一省份核心流水线"""
    province = extract_province(template_filename)
    if not province:
        print(f"[-] 无法从文件名中识别省份: {template_filename}")
        return False
    
    # 同时提取运营商（支持从文件名和目录名识别）
    isp = detect_isp(template_filename, TEMPLATE_DIR)
    region = f"{province}-{isp}"

    # 确保output目录存在
    if not os.path.exists('output'):
        os.makedirs('output')

    template_path = os.path.join(TEMPLATE_DIR, template_filename)
    out_txt = os.path.join('output', template_filename) 
    out_m3u = os.path.join('output', template_filename.replace('.txt', '.m3u'))

    # 1. 检测已有文件（如果不是强制生成模式）
    if not FORCE_GENERATE and check_and_clear_existing(out_txt, out_m3u):
        return False

    # 2. 读取母版内容
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except Exception as e:
        print(f"[-] 读取模板文件失败: {e}")
        return False
    
    # 动态嗅探组播地址 (自动识别 udp/rtp/igmp 及纯组播地址)
    # 优先匹配带协议前缀的地址
    match = re.search(r'(?:https?://[^/,]+/)?(udp|rtp|igmp)(?:/|://)(\d+\.\d+\.\d+\.\d+:\d+)', template_content, re.IGNORECASE)
    if not match:
        # 如果没有匹配到，尝试匹配纯组播地址（任意IP开头，带端口）
        match = re.search(r'(\d+\.\d+\.\d+\.\d+:\d+)', template_content, re.IGNORECASE)
        if match:
            # 纯组播地址默认使用 rtp 协议
            protocol = "rtp"
            mcast_target = match.group(1)
        else:
            print(f"[-] 无法从模板文件中提取组播地址: {template_filename}")
            return False
    else:
        protocol, mcast_target = match.group(1).lower(), match.group(2)
    print(f"[*] 成功提取 [{region}] 测试地址: /{protocol}/{mcast_target}")

    # 3. 获取资产并绝对去重
    if DATA_SOURCE == "quake":
        assets = get_quake_assets(province, isp)
    else:
        assets = get_local_assets(province, isp)
    if not assets:
        print(f"[-] 未获取到 [{region}] 的节点信息")
        return False

    urls_to_test, host_map, seen_hosts = [], {}, set()
    for item in assets:
        domain = item.get('domain') or item.get('service', {}).get('http', {}).get('host') or item.get('hostname')
        port = item.get('port')
        if domain and port:
            full_host = f"{domain}:{port}"
            if full_host not in seen_hosts:
                seen_hosts.add(full_host)
                test_url = f"http://{full_host}/{protocol}/{mcast_target}"
                urls_to_test.append(test_url)
                host_map[test_url] = full_host
    
    if not urls_to_test:
        print(f"[-] 没有找到有效的节点URL")
        return False
    
    print(f"[*] 去重后共发现 {len(urls_to_test)} 个节点")
    
    valid_hosts = []
    
    if ENABLE_SERVER_TEST:
        print("[*] 开始测试服务器...")
        # 4. 并发深度测流
        valid_hosts_with_speed = []
        with ThreadPoolExecutor(max_workers=TEST_MAX_WORKERS) as executor:
            for res_url, speed in executor.map(check_url, urls_to_test):
                if res_url:
                    valid_hosts_with_speed.append((host_map[res_url], speed))
        
        # 按速度排序（耗时越短，速度越快）
        valid_hosts_with_speed.sort(key=lambda x: x[1])
        valid_hosts = [host for host, _ in valid_hosts_with_speed]
        
        # 限制使用的服务器数量
        if len(valid_hosts) > GENERATE_MAX_SERVERS:
            valid_hosts = valid_hosts[:GENERATE_MAX_SERVERS]
            print(f"[*] 节点测试完成，已按速度排序，限制使用前 {GENERATE_MAX_SERVERS} 个服务器")
        elif valid_hosts:
            print(f"[*] 节点测试完成，已按速度排序，使用全部 {len(valid_hosts)} 个服务器")
    else:
        # 不进行测速，直接使用去重后的服务器（按原始顺序）
        valid_hosts = [host_map[url] for url in urls_to_test]
        # 限制使用的服务器数量
        if len(valid_hosts) > GENERATE_MAX_SERVERS:
            valid_hosts = valid_hosts[:GENERATE_MAX_SERVERS]
            print(f"[*] 不进行测速，使用前 {GENERATE_MAX_SERVERS} 个服务器（按原始顺序）")
        else:
            print(f"[*] 不进行测速，使用全部 {len(valid_hosts)} 个服务器（按原始顺序）")

    # 5. 克隆母版生成纯净文件
    if valid_hosts:
        pattern = re.compile(r'(?:https?://[^/,]+/)?(udp|rtp|igmp)(?:/|://)(\d+\.\d+\.\d+\.\d+:\d+)', re.IGNORECASE)
        try:
            print(f"[*] 开始生成直播源文件...")
            
            # 加载频道分类配置
            alias_to_channel, channel_info, category_order = load_category_config()
            
            # 生成更新时间的行
            update_time = time.strftime('%Y/%m/%d %H:%M')
            update_line = f"更新时间,#genre#\n{update_time},https://taoiptv.com/time.mp4\n"
            
            # 生成 m3u 格式的更新时间行
            update_line_m3u = f"#EXTINF:-1 group-title=\"更新时间\",{update_time}\nhttps://taoiptv.com/time.mp4\n"
            
            # 解析模板文件，收集频道信息
            channels_data = []
            template_lines = template_content.strip().split('\n')
            current_group = "未分类"
            
            for line in template_lines:
                line = line.strip()
                if not line:
                    continue
                
                if '#genre#' in line:
                    current_group = line.split(',')[0].strip()
                elif ',' in line:
                    parts = line.split(',', 2)
                    
                    if len(parts) == 3:
                        # 3列格式：分类,频道名,组播地址
                        category_from_line = parts[0].strip()
                        name = parts[1].strip()
                        address = parts[2].strip()
                        # 使用行中的分类覆盖当前分组
                        if category_from_line:
                            current_group = category_from_line
                    elif len(parts) == 2:
                        # 2列格式：频道名,地址
                        name = parts[0].strip()
                        address = parts[1].strip()
                    else:
                        continue
                    
                    # 标准化频道名
                    normalized_name = normalize_channel_name(name, alias_to_channel)
                    # 获取配置中的分类，如果没有则使用当前分组
                    if normalized_name in channel_info:
                        config_category = channel_info[normalized_name][0]
                        channel_id = channel_info[normalized_name][1]
                    else:
                        config_category = current_group
                        channel_id = None
                    
                    channels_data.append({
                        'original_name': name,
                        'normalized_name': normalized_name,
                        'address': address,
                        'category': config_category,
                        'channel_id': channel_id
                    })
            
            # 创建分类到顺序的映射，不在配置中的分类放最后
            category_index = {cat: idx for idx, cat in enumerate(category_order)}
            max_index = len(category_order)
            
            # 按分类顺序、频道ID、频道名排序
            channels_data.sort(key=lambda x: (
                category_index.get(x['category'], max_index),
                x['channel_id'] or '',
                x['normalized_name']
            ))
            
            with open(out_txt, 'w', encoding='utf-8') as f_txt, open(out_m3u, 'w', encoding='utf-8') as f_m3u:
                f_m3u.write("#EXTM3U\n")
                
                # 按分类分组输出
                last_category = None
                for channel in channels_data:
                    category = channel['category']
                    normalized_name = channel['normalized_name']
                    address = channel['address']
                    
                    # 写入分类标记
                    if category != last_category:
                        f_txt.write(f"{category},#genre#\n")
                        last_category = category
                    
                    # 为每个服务器生成该行
                    for host in valid_hosts:
                        # 检查地址是否已有协议前缀
                        has_protocol = address.startswith('rtp://') or address.startswith('udp://') or address.startswith('http://')
                        if has_protocol:
                            new_address = pattern.sub(f'http://{host}/\\1/\\2', address)
                        else:
                            # 纯组播地址，添加 rtp:// 前缀
                            new_address = f"http://{host}/rtp/{address}"
                        f_txt.write(f"{normalized_name},{new_address}\n")
                        f_m3u.write(f'#EXTINF:-1 group-title="{category}",{normalized_name}\n{new_address}\n')
                
                f_txt.write("\n")
                f_m3u.write("\n")
                
                # 添加更新时间行
                f_txt.write(update_line)
                f_m3u.write(update_line_m3u)
            print(f"  - [{region}] 更新完成，获取 {len(valid_hosts)} 个纯净节点。")
            print(f"  - 已生成 2 个播放列表文件:")
            print(f"    - output/{template_filename}")
            print(f"    - output/{template_filename.replace('.txt', '.m3u')}")
            return True
        except Exception as e:
            print(f"[-] 生成文件失败: {e}")
            return False
    else:
        print(f"[-] [{region}] 本次联网搜索UDPXY服务器失败。")
        return False

def push_to_gitee(filename):
    """
    Gitee 终极同步模块（修复中文乱码与新建/更新分离机制）
    """
    if not os.path.exists(filename): 
        print(f"[-] 文件 [{filename}] 不存在，跳过 Gitee 推送")
        return
    
    # 检查 Gitee 配置是否完整
    if not GITEE_TOKEN or GITEE_TOKEN.startswith("填入") or not GITEE_USER or not GITEE_REPO:
        print(f"[-] Gitee 配置不完整，跳过推送 [{filename}]")
        return 
    
    # 确保只处理output目录下的文件
    if not filename.startswith('output'):
        print(f"[-] 只上传output目录下的文件，跳过 [{filename}]")
        return

    print(f"\n[*] 正在将 [{filename}] 同步推送至 Gitee 仓库...")
    
    # 尝试不同编码读取文件
    content = ""
    encodings = ['utf-8', 'gbk', 'gb2312', 'ansi']
    for encoding in encodings:
        try:
            with open(filename, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    
    if not content:
        print(f"[-] 无法读取文件 [{filename}]，跳过推送")
        return
    
    b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    g_user = GITEE_USER.strip()
    g_repo = GITEE_REPO.strip()
    g_branch = GITEE_BRANCH.strip()
    
    # 处理文件路径，确保上传到远程的output目录
    # 提取文件名
    file_name = os.path.basename(filename)
    # 构建远程路径：output/文件名
    remote_path = f"output/{file_name}"
    
    # 对远程路径进行URL编码
    safe_remote_path = urllib.parse.quote(remote_path)
    api_url = f"https://gitee.com/api/v5/repos/{g_user}/{g_repo}/contents/{safe_remote_path}"

    sha = ""
    remote_content = ""
    try:
        # 获取文件信息
        get_resp = requests.get(api_url, params={"access_token": GITEE_TOKEN, "ref": g_branch}, timeout=10)
        if get_resp.status_code == 200:
            resp_data = get_resp.json()
            # 防御性验证，就算被解析成了 list 也要安全遍历提取 sha
            if isinstance(resp_data, dict):
                sha = resp_data.get("sha", "")
                # 获取远程文件内容
                if "content" in resp_data:
                    remote_content = resp_data.get("content", "")
                    if remote_content:
                        try:
                            remote_content = base64.b64decode(remote_content).decode('utf-8')
                        except:
                            remote_content = ""
            elif isinstance(resp_data, list):
                for item in resp_data:
                    if item.get("name") == file_name:
                        sha = item.get("sha", "")
                        if "content" in item:
                            remote_content = item.get("content", "")
                            if remote_content:
                                try:
                                    remote_content = base64.b64decode(remote_content).decode('utf-8')
                                except:
                                    remote_content = ""
                        break
    except Exception as e:
        print(f"[-] 获取文件状态异常: {e}")

    # 比较本地内容和远程内容
    if sha and remote_content == content:
        print(f"[*] 文件 [{file_name}] 未变化，跳过推送")
        # 更新本地记录（远程已存在相同内容，本地记录也要同步）
        update_push_record(filename, content)
        return

    payload = {
        "access_token": GITEE_TOKEN,
        "content": b64_content,
        "message": f"Auto update {file_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    }

    try:
        if sha:
            # 有 sha 代表文件存在，必须使用 PUT 进行更新
            payload["sha"] = sha 
            put_resp = requests.put(api_url, json=payload, timeout=15)
            status_code = put_resp.status_code
            resp_text = put_resp.text
        else:
            # 没有 sha 代表这是个新文件，必须使用 POST 进行新建！(Gitee的特殊要求)
            post_resp = requests.post(api_url, json=payload, timeout=15)
            status_code = post_resp.status_code
            resp_text = post_resp.text

        if status_code in [200, 201]:
            if sha:
                print(f"[+]  成功！[{file_name}] 已更新到 Gitee 仓库的 output 目录！")
            else:
                print(f"[+]  成功！[{file_name}] 已新建到 Gitee 仓库的 output 目录！")
            # 推送成功后更新本地记录
            update_push_record(filename, content)
        else:
            print(f"[-] 推送失败，Gitee 响应: {resp_text}")
    except Exception as e:
        print(f"[!] 推送请求出错: {e}")
        
    # 加入0.5秒延迟，防止密集提交触发 Gitee 并发拦截
    time.sleep(0.5)

def push_to_github(filename):
    """
    GitHub 同步模块
    """
    if not os.path.exists(filename): 
        print(f"[-] 文件 [{filename}] 不存在，跳过 GitHub 推送")
        return
    
    # 检查 GitHub 配置是否完整
    if not GITHUB_TOKEN or not GITHUB_USER or not GITHUB_REPO:
        print(f"[-] GitHub 配置不完整，跳过推送 [{filename}]")
        return 
    
    # 确保只处理output目录下的文件
    if not filename.startswith('output'):
        print(f"[-] 只上传output目录下的文件，跳过 [{filename}]")
        return

    print(f"\n[*] 正在将 [{filename}] 同步推送至 GitHub 仓库...")
    
    # 尝试不同编码读取文件
    content = ""
    encodings = ['utf-8', 'gbk', 'gb2312', 'ansi']
    for encoding in encodings:
        try:
            with open(filename, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    
    # 提取文件名
    file_name = os.path.basename(filename)
    
    g_user = GITHUB_USER.strip()
    g_repo = GITHUB_REPO.strip()
    g_branch = GITHUB_BRANCH.strip()
    
    # 处理文件路径，确保上传到远程的output目录
    # 构建远程路径：output/文件名
    remote_path = f"output/{file_name}"
    
    # 对远程路径进行URL编码
    safe_remote_path = urllib.parse.quote(remote_path)
    api_url = f"https://api.github.com/repos/{g_user}/{g_repo}/contents/{safe_remote_path}"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    sha = ""
    remote_content = ""
    try:
        # 获取文件信息
        get_resp = requests.get(api_url, params={"ref": g_branch}, headers=headers, timeout=10)
        if get_resp.status_code == 200:
            resp_data = get_resp.json()
            if isinstance(resp_data, dict):
                sha = resp_data.get("sha", "")
                # 获取远程文件内容
                if "content" in resp_data:
                    remote_content = resp_data.get("content", "")
                    if remote_content:
                        try:
                            import base64 as b64_module
                            remote_content = b64_module.b64decode(remote_content).decode('utf-8')
                        except:
                            remote_content = ""
    except Exception as e:
        print(f"[-] 获取文件状态异常: {e}")

    # 比较本地内容和远程内容
    if sha and remote_content == content:
        print(f"[*] 文件 [{file_name}] 未变化，跳过推送")
        # 更新本地记录（远程已存在相同内容，本地记录也要同步）
        update_push_record(filename, content)
        return

    import base64 as b64_module
    b64_content = b64_module.b64encode(content.encode('utf-8')).decode('utf-8')

    payload = {
        "message": f"Auto update {file_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "content": b64_content,
        "branch": g_branch
    }

    try:
        if sha:
            # 有 sha 代表文件存在，必须使用 PUT 进行更新
            payload["sha"] = sha 
            put_resp = requests.put(api_url, json=payload, headers=headers, timeout=15)
            status_code = put_resp.status_code
            resp_text = put_resp.text
        else:
            # 没有 sha 代表这是个新文件
            post_resp = requests.put(api_url, json=payload, headers=headers, timeout=15)
            status_code = post_resp.status_code
            resp_text = post_resp.text

        if status_code in [200, 201]:
            if sha:
                print(f"[+]  成功！[{file_name}] 已更新到 GitHub 仓库的 output 目录！")
            else:
                print(f"[+]  成功！[{file_name}] 已新建到 GitHub 仓库的 output 目录！")
            # 推送成功后更新本地记录
            update_push_record(filename, content)
        else:
            print(f"[-] 推送失败，GitHub 响应: {resp_text}")
    except Exception as e:
        print(f"[!] 推送请求出错: {e}")
        
    # 加入0.5秒延迟，防止密集提交触发 GitHub 并发拦截
    time.sleep(0.5)

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 显示欢迎信息
    print("=" * 70)
    print("      UDPXY IPTV源管理工具 - 开始执行")
    print("=" * 70)
    
    # 显示配置信息
    print("\n[*] 配置信息:")
    print(f"    数据源: {DATA_SOURCE}")
    print(f"    模板目录: {TEMPLATE_DIR}")
    print(f"    强制生成: {'是' if FORCE_GENERATE else '否'}")
    if DATA_SOURCE == "quake":
        print(f"    Quake Token: {'已配置' if QUAKE_TOKEN and not QUAKE_TOKEN.startswith('填入') else '未配置'}")
    else:
        print(f"    本地节点文件: {LOCAL_NODES_FILE}")
    print(f"    Gitee 推送: {'已配置' if GITEE_TOKEN and not GITEE_TOKEN.startswith('填入') and GITEE_USER and GITEE_REPO else '未配置'}")
    print(f"    GitHub 推送: {'已配置' if GITHUB_TOKEN and GITHUB_USER and GITHUB_REPO else '未配置'}")
    
    push_enabled = GITEE_AUTO_PUSH or GITHUB_AUTO_PUSH
    print(f"    自动推送: {'开启' if push_enabled else '关闭'}")
    
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        print(f"\n[!] 没有找到 '{TEMPLATE_DIR}' 目录，已自动创建。")
        print(f"[!] 请在 '{TEMPLATE_DIR}' 目录中放入各省市的模板文件后重新运行！")
        return

    template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith('.txt')]
    if not template_files:
        print(f"\n[!] '{TEMPLATE_DIR}' 目录中空空如也，请放入各省市的模板文件。")
        return
    
    print(f"\n[*] '{TEMPLATE_DIR}' 目录中发现 {len(template_files)} 个模板文件，开始处理...")

    # 流水线处理各省份
    processed_count = 0
    success_count = 0
    isps_seen = set()
    for i, filename in enumerate(template_files, 1):
        print(f"\n" + "="*70)
        print(f"  [{i}/{len(template_files)}] 正在处理: {filename}")
        print("="*70)
        # 提取运营商信息用于统计
        isp = detect_isp(filename, TEMPLATE_DIR)
        isps_seen.add(isp)
        result = process_province(filename)
        processed_count += 1
        if result:
            success_count += 1
    
    print(f"\n" + "="*70)
    print(f"  本地文件生成完成")
    print(f"  处理省份: {processed_count}")
    print(f"  处理运营商: {len(isps_seen)}")
    print(f"  成功更新: {success_count}")
    print("="*70)

    # 遍历output目录下生成的最新源文件，推送到云端仓库
    print("\n[*] 准备执行云端同步...")
    
    push_enabled = GITEE_AUTO_PUSH or GITHUB_AUTO_PUSH
    if not push_enabled:
        print("[-] 自动推送已禁用，跳过云端同步")
    elif os.path.exists('output'):
        gitee_files = [os.path.join('output', f) for f in os.listdir('output') if f.endswith('.txt') or f.endswith('.m3u')]
        if gitee_files:
            print(f"[*] 发现 {len(gitee_files)} 个文件待推送")
            if GITEE_AUTO_PUSH:
                print("\n[*] 开始推送到 Gitee...")
                for file in gitee_files:
                    push_to_gitee(file)
            if GITHUB_AUTO_PUSH:
                print("\n[*] 开始推送到 GitHub...")
                for file in gitee_files:
                    push_to_github(file)
        else:
            print("[-] output目录中没有发现可推送的文件")
    else:
        print("[-] output目录不存在，跳过云端同步")

    print("\n" + "="*70)
    print("  处理完成！")
    # 根据设置生成动态流程描述
    flow_parts = []
    if DATA_SOURCE == "local":
        flow_parts.append("读取本地节点")
    else:
        flow_parts.append("全网搜源")
    flow_parts.append("深度测流")
    flow_parts.append("覆盖生成")
    if GITEE_AUTO_PUSH:
        flow_parts.append("云端发布")
    print(f"  流程: {' -> '.join(flow_parts)}")
    print(f"  日志文件: log/build_udpxy_playlist_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    print("="*70)

if __name__ == '__main__':
    main()