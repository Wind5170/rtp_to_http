import requests
import re
import time
import sys
import os
import argparse
import tkinter as tk
from tkinter import filedialog
from concurrent.futures import ThreadPoolExecutor
import threading
KNOWN_REGIONS = {"江苏", "上海", "浙江", "广东", "北京", "四川", "山东", "福建", "贵州", "重庆", "青海", "广西", "湖南", "宁夏", "云南", "内蒙", "天津", "安徽", "山西", "江西", "河北", "河南", "海南", "湖北", "甘肃", "辽宁", "吉林", "陕西", "黑龙江", "新疆"}
MAX_SERVERS = 30  # 默认最大服务器数量
FORCE_TEST_ALL = True  # 是否强制测试所有地址

def test_multicast_url(multicast_url, udpxy_server):
    try:
        match = re.search(r'(rtp|udp)://([\d.]+):(\d+)', multicast_url)
        if not match:
            return multicast_url, False, "格式错误", ""

        protocol, ip, port = match.groups()
        # 移除服务器地址中的 http:// 前缀，避免重复
        server_clean = udpxy_server.replace('http://', '').replace('https://', '')
        udpxy_url = f"http://{server_clean}/{protocol}/{ip}:{port}"

        start_time = time.time()
        with requests.get(udpxy_url, stream=True, timeout=(3, 5)) as resp:
            if resp.status_code == 200:
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                    if downloaded >= 16384:
                        end_time = time.time()
                        speed = end_time - start_time
                        return multicast_url, True, f"耗时: {speed:.2f}s", udpxy_url
                end_time = time.time()
                return multicast_url, False, f"下载不足16KB", udpxy_url
            else:
                return multicast_url, False, f"状态码: {resp.status_code}", udpxy_url
    except Exception as e:
        return multicast_url, False, f"错误", udpxy_url

def extract_region_from_filename(file_path):
    basename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(basename)[0]
    
    region = None
    isp = None
    
    # 首先从文件名判断地区
    for r in KNOWN_REGIONS:
        if r in name_without_ext:
            region = r
            break
    
    # 如果文件名没有，从目录名判断地区
    if not region:
        dirname = os.path.dirname(file_path)
        dir_basename = os.path.basename(dirname)
        for r in KNOWN_REGIONS:
            if r in dir_basename:
                region = r
                break
    
    # 提取ISP
    isp_keywords = {"电信": "电信", "移动": "移动", "联通": "联通"}
    for keyword, value in isp_keywords.items():
        if keyword in name_without_ext:
            isp = value
            break
    if not isp:
        dirname = os.path.dirname(file_path)
        dir_basename = os.path.basename(dirname)
        for keyword, value in isp_keywords.items():
            if keyword in dir_basename:
                isp = value
                break
    
    return region, isp

def is_valid_multicast_addr(addr):
    """检查是否是有效的组播地址"""
    if not addr:
        return False
    if addr.startswith('#'):
        return False
    if addr.startswith('rtp://') or addr.startswith('udp://'):
        return True
    if ':' in addr and addr.count('.') >= 2:
        return True
    return False

def parse_multicast_file(file_path, default_region=None):
    items = {}
    found_region_marker = False
    current_category = default_region if default_region else "未分类"

    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
    lines = None
    detected_encoding = None
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
            detected_encoding = encoding
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return None, None, str(e)

    if lines is None:
        return None, None, "无法读取文件"

    for line in lines:
        line = line.rstrip('\n')
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith('#'):
            continue
        elif ',' in stripped:
            parts = stripped.split(',', 3)  # 最多分割为4部分
            tag = ""
            
            if len(parts) >= 4:
                # 四段式格式：分类,频道名,组播地址,标签
                category_part = parts[0].strip()
                name = parts[1].strip()
                addr = parts[2].strip()
                tag = parts[3].strip()
            elif len(parts) == 3:
                # 三段式格式：分类,频道名,组播地址
                category_part = parts[0].strip()
                name = parts[1].strip()
                addr = parts[2].strip()
            elif len(parts) == 2:
                # 两段式格式：分类标记行或频道名,地址
                second_part = parts[1].strip()
                
                # 检查是否是分类标记行（格式：分类名,#genre#）
                if second_part == '#genre#' or second_part.startswith('#genre'):
                    # 设置当前分类，不参与测试
                    current_category = parts[0].strip() or current_category
                    continue
                elif is_valid_multicast_addr(second_part):
                    # 格式：频道名,地址（使用当前分类）
                    category_part = current_category
                    name = parts[0].strip()
                    addr = second_part
                else:
                    # 格式：频道名,地址（使用当前分类）
                    category_part = current_category
                    name = parts[0].strip()
                    addr = second_part
            else:
                continue
            
            # 跳过无效的组播地址（如 #genre# 等）
            if not is_valid_multicast_addr(addr):
                continue
            
            # 确保分类不为空
            if not category_part:
                category_part = default_region if default_region else "未分类"
            
            # 如果分类不存在，创建新分类
            if category_part not in items:
                items[category_part] = {"active": [], "failed": []}
            
            # 处理组播地址，添加 rtp:// 前缀如果缺失
            if addr and not addr.startswith('rtp://') and not addr.startswith('udp://'):
                addr = 'rtp://' + addr
            
            if addr.startswith('rtp://') or addr.startswith('udp://'):
                # 根据标签判断是有效还是无效
                if tag == "无效":
                    items[category_part]["failed"].append({"name": name, "addr": addr})
                else:
                    items[category_part]["active"].append({"name": name, "addr": addr})
        elif is_valid_multicast_addr(stripped):
            category_part = default_region if default_region else "未分类"
            if category_part not in items:
                items[category_part] = {"active": [], "failed": []}
            addr = stripped if stripped.startswith('rtp://') or stripped.startswith('udp://') else f'rtp://{stripped}'
            items[category_part]["active"].append({"name": "", "addr": addr})

    return items, detected_encoding, found_region_marker

def parse_servers_by_region(server_file):
    servers_by_region = {}

    try:
        with open(server_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    continue
                
                parts = line.split(',')
                isp = None
                region_name = None
                server = None
                
                if len(parts) >= 3:
                    # 3列格式：运营商,省份,服务器地址
                    isp = parts[0].strip()
                    region_name = parts[1].strip()
                    server = parts[2].strip()
                elif len(parts) >= 2:
                    # 2列格式：省份,服务器地址（向后兼容）
                    region_name = parts[0].strip()
                    server = parts[1].strip()
                
                if region_name and server and region_name in KNOWN_REGIONS and ':' in server:
                    if region_name not in servers_by_region:
                        servers_by_region[region_name] = []
                    servers_by_region[region_name].append(server)
                elif ':' in line:
                    pass
    except Exception as e:
        print(f"读取服务器列表失败: {e}")
        return {}

    return servers_by_region

def main():
    global MAX_SERVERS, FORCE_TEST_ALL
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='组播地址健康检查工具')
    parser.add_argument('-f', '--file', help='组播地址文件路径')
    parser.add_argument('-s', '--servers', type=int, default=MAX_SERVERS,
                        help=f'最大服务器数量（默认: {MAX_SERVERS}）')
    parser.add_argument('-a', '--all', action='store_true', default=FORCE_TEST_ALL,
                        help=f'是否强制测试所有地址（默认: {FORCE_TEST_ALL}）')
    args = parser.parse_args()
    
    max_servers = args.servers
    force_test_all = args.all
    
    default_dir = "multicast_addresses/collected"
    
    # 使用 tkinter 文件对话框选择文件
    root = tk.Tk()
    root.withdraw()
    
    multicast_file = ""
    if args.file and os.path.exists(args.file):
        multicast_file = args.file
        print(f"已通过参数指定文件: {multicast_file}")
    else:
        multicast_file = filedialog.askopenfilename(
            title="选择组播地址文件",
            initialdir=default_dir,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
    
    if not multicast_file:
        print("未选择文件，退出程序")
        return
    
    # 规范化路径显示
    multicast_file = multicast_file.replace('\\', '/')
    
    # 从文件名或目录名判断组播地区和ISP
    default_region, default_isp = extract_region_from_filename(multicast_file)
    
    if not default_region:
        print(f"错误: 无法从文件名 '{os.path.basename(multicast_file)}' 或目录名 '{os.path.basename(os.path.dirname(multicast_file))}' 中检测到地区信息")
        print("请确保文件名或目录名包含以下地区关键字之一：")
        print(", ".join(sorted(KNOWN_REGIONS)))
        return

    print(f"\n读取组播地址文件: {multicast_file}")
    print(f"检测到组播地区: {default_region}")
    print(f"检测到运营商(ISP): {default_isp or '未知'}")
    items, detected_encoding, found_region_marker = parse_multicast_file(multicast_file, default_region)
    if items is None:
        print(f"错误: {detected_encoding}")
        return

    if not items:
        print("错误: 没有找到组播地址")
        return

    udpxy_server_file = "nodes.txt"
    print(f"\n读取 udpxy 服务器列表: {udpxy_server_file}")
    servers_by_region = parse_servers_by_region(udpxy_server_file)
    
    if not servers_by_region:
        print("错误: 服务器列表为空")
        return
    
    # 只使用匹配地区的服务器
    if default_region not in servers_by_region:
        print(f"错误: 没有找到 {default_region} 地区的可用服务器")
        return
    
    print(f"使用 {default_region} 地区的服务器进行测试")

    total_active = sum(len(r["active"]) for r in items.values())
    total_failed = sum(len(r["failed"]) for r in items.values())

    print(f"\n共发现 {len(items)} 个分类的组播地址")
    print(f"活动组播地址: {total_active} 个", end="")
    if total_failed > 0:
        print(f"，前一次测试无效地址: {total_failed} 个")
    else:
        print()
    if force_test_all:
        print(f"共测试地址: {total_active + total_failed} 个")
    print(f"最大服务器数量: {max_servers}")
    
    # 选择服务器（只使用匹配地区的服务器）
    region_servers = servers_by_region[default_region]
    region_servers = region_servers[:max_servers]  # 最多max_servers个服务器
    num_servers = len(region_servers)
    
    if num_servers == 0:
        print("错误: 没有可用的服务器")
        return
    
    # 收集所有要测试的项目（包含分类信息）
    all_test_items = []
    for category, data in items.items():
        test_items = data["active"].copy()
        if force_test_all:
            test_items.extend(data["failed"])
        # 为每个item添加分类信息
        for item in test_items:
            item["category"] = category
        all_test_items.extend(test_items)
    
    num_items = len(all_test_items)
    if num_items == 0:
        print("错误: 没有要测试的地址")
        return
    
    script_dir = os.path.dirname(__file__)
    rel_path = os.path.relpath(multicast_file, script_dir)
    rel_dir = os.path.dirname(rel_path)
    file_basename = os.path.splitext(os.path.basename(multicast_file))[0]
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    
    log_file = os.path.normpath(os.path.join(rel_dir, f"{file_basename}_{timestamp}.log"))
    valid_file = os.path.normpath(os.path.join(rel_dir, f"{file_basename}_{timestamp}.txt"))

    class Logger:
        def __init__(self, filename):
            self.console = sys.stdout
            self.file = open(filename, 'w', encoding='utf-8')

        def write(self, message):
            self.console.write(message)
            self.file.write(message)

        def flush(self):
            self.console.flush()
            self.file.flush()

    sys.stdout = Logger(log_file)

    results = {}
    active_invalid = []
    valid_failed = []
    invalid_failed = []
    valid_results = []
    
    items_per_server = (num_items + num_servers - 1) // num_servers
    server_groups = []
    
    for i in range(num_servers):
        start = i * items_per_server
        end = min(start + items_per_server, num_items)
        if start < end:
            server_groups.append({
                "server": region_servers[i],
                "items": all_test_items[start:end]
            })

    print(f"\n开始测试...")
    print(f"  服务器数: {num_servers} 个")
    print(f"  组播地址数: {num_items} 个")
    print(f"  分组策略: 每个服务器测试约 {items_per_server} 个地址")
    print(f"  并发数: {num_servers} 个")

    print_lock = threading.Lock()

    def test_server_group(group):
        server = group["server"]
        group_valid = 0
        group_results = []
        
        for item in group["items"]:
            addr = item["addr"]
            name = item.get("name", "")
            
            result = test_multicast_url(addr, server)
            multicast_url, is_valid, status, test_url = result
            
            if name:
                display_name = f"{name}"
            else:
                display_name = addr
            
            if is_valid:
                with print_lock:
                    print(f"  [√] [{display_name}][{addr}] - {status}")
                # 提取速度信息（格式：耗时: 0.28s）
                speed = 9999.0
                if "耗时:" in status:
                    try:
                        speed = float(status.replace("耗时:", "").replace("s", "").strip())
                    except:
                        pass
                result_item = item.copy()
                result_item["speed"] = speed
                valid_results.append(result_item)
            else:
                with print_lock:
                    print(f"  [×] [{display_name}][{addr}] - {status}")
                active_invalid.append(item)
            group_results.append(result)
        
        return server, group_valid, group_results

    with ThreadPoolExecutor(max_workers=num_servers) as executor:
        executor.map(test_server_group, server_groups)

    print("\n" + "=" * 80)
    
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 生成1：每个测试文件的测试结果（覆盖模式）
    health_checked_file = os.path.normpath(os.path.join(rel_dir, f"{file_basename}_health_checked.txt"))
    print(f"写入测试结果到 {health_checked_file}")
    try:
        with open(health_checked_file, 'w', encoding='utf-8') as f:
            f.write(f"# 生成时间: {timestamp}\n\n")
            
            for category, data in items.items():
                # 写入有效地址
                for item in data["active"]:
                    if item["addr"] in [r["addr"] for r in valid_results]:
                        status = "有效"
                    elif item["addr"] in [r["addr"] for r in active_invalid]:
                        status = "无效"
                    else:
                        status = ""
                    f.write(f"{category},{item['name']},{item['addr']},{status}\n")
                
                # 写入无效地址（如果强制测试所有）
                if force_test_all:
                    for item in data["failed"]:
                        if item["addr"] in [r["addr"] for r in valid_results]:
                            status = "有效"
                        elif item["addr"] in [r["addr"] for r in active_invalid]:
                            status = "无效"
                        else:
                            status = ""
                        f.write(f"{category},{item['name']},{item['addr']},{status}\n")
        print(f"成功写入 {health_checked_file}")
    except Exception as e:
        print(f"写入文件失败: {e}")
    
    # 生成2：健康检查后有效的组播地址（追加模式，去重）
    # 使用之前已经识别的地区和ISP
    region = default_region or "未知"
    isp = default_isp or "未知"
    curated_dir = os.path.normpath("multicast_addresses/curated")
    os.makedirs(curated_dir, exist_ok=True)
    curated_file = os.path.normpath(os.path.join(curated_dir, f"{region}_{isp}_valid_multicast.txt"))
    
    print(f"\n写入有效组播地址到 {curated_file}")
    
    # 读取现有文件，建立地址到分类的映射（分类分级：未分类最低级）
    existing_addrs = {}
    if os.path.exists(curated_file):
        try:
            with open(curated_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(',', 3)
                    if len(parts) >= 3:
                        existing_category = parts[0].strip()
                        existing_name = parts[1].strip()
                        existing_addr = parts[2].strip()
                        existing_addrs[existing_addr] = {"category": existing_category, "name": existing_name}
        except Exception as e:
            print(f"读取现有文件失败: {e}")
    
    # 按测试速度排序（耗时越短越好）
    valid_results.sort(key=lambda x: x.get("speed", 9999.0))
    
    # 构建有效地址集合和映射
    valid_addrs_info = {item["addr"]: item for item in valid_results}
    
    # 合并新的有效地址（去重）
    for addr, item in valid_addrs_info.items():
        if addr not in existing_addrs:
            category = item.get("category", "未分类")
            name = item.get("name", "")
            existing_addrs[addr] = {"category": category, "name": name}
        else:
            # 分类分级判断：未分类最低级
            existing_category = existing_addrs[addr]["category"]
            new_category = item.get("category", "未分类")
            if existing_category == "未分类" and new_category != "未分类":
                existing_addrs[addr]["category"] = new_category
                existing_addrs[addr]["name"] = item.get("name", "")
    
    # 写入到curated文件
    try:
        with open(curated_file, 'w', encoding='utf-8') as f:
            f.write(f"# 生成时间: {timestamp}\n")
            
            for addr, info in existing_addrs.items():
                f.write(f"{info['category']},{info['name']},{addr}\n")
        print(f"成功写入 {curated_file}")
    except Exception as e:
        print(f"写入curated文件失败: {e}")

    # 生成3：复制有效组播文件到multicast_addresses\active目录
    # 文件名格式：地区+运营商，无连接符，如：江苏电信.txt
    source_multicast_dir = os.path.normpath("multicast_addresses/active")
    os.makedirs(source_multicast_dir, exist_ok=True)
    source_multicast_file = os.path.join(source_multicast_dir, f"{region}{isp}.txt")
    
    print(f"\n复制有效组播文件到 {source_multicast_file}")
    
    try:
        with open(source_multicast_file, 'w', encoding='utf-8') as f:
            f.write(f"# 生成时间: {timestamp}\n")
            
            for addr, info in existing_addrs.items():
                f.write(f"{info['category']},{info['name']},{addr}\n")
        print(f"成功写入 {source_multicast_file}")
    except Exception as e:
        print(f"写入multicast_addresses/active文件失败: {e}")

    print("=" * 80)
    total_valid = len(valid_results) + len(valid_failed)
    total_invalid = len(active_invalid) + len(invalid_failed)
    total_test = total_active + total_failed if force_test_all else total_active
    print(f"测试完成: 有效 {total_valid}, 无效 {total_invalid}, 总计 {total_test}")
    if force_test_all and valid_failed:
        print(f"有 {len(valid_failed)} 个测试失败的地址通过测试")
    print("=" * 80)

    sys.stdout = sys.stdout.console
    print(f"测试完成，详细日志已保存到 {log_file}")

if __name__ == "__main__":
    main()