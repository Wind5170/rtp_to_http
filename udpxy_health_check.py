import requests
import re
import time
import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor

MAX_WORKERS = 30
TEST_PROTOCOL = "rtp"  # 测试协议，可选 rtp 或 udp
NODES_OUTPUT_MODE = 1  # nodes.txt生成模式：0-不生成，1-追加生成，2-覆盖生成
TEST_INVALID_SERVERS = False  # 是否测试标记为"无效"的服务器 True


def select_udpxy_files(default_dir="udpxy_servers/collected"):
    """通过对话框选择多个udpxy服务器地址列表文件，支持备用命令行输入"""
    files = []
    
    # 首先尝试使用tkinter对话框
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        root.attributes('-topmost', True)  # 置顶窗口
        
        initial_dir = default_dir if os.path.exists(default_dir) else "."
        
        file_paths = filedialog.askopenfilenames(
            title="选择udpxy服务器地址列表文件（可多选）",
            initialdir=initial_dir,
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        root.destroy()
        
        if file_paths:
            files = list(file_paths)
            
    except Exception as e:
        print(f"无法打开文件选择对话框: {e}")
        print("将使用命令行输入方式...")
    
    # 如果通过对话框没有选择文件，使用命令行输入
    if not files:
        print(f"\n请输入udpxy服务器地址列表文件路径（默认目录: {default_dir}）")
        print("可以输入多个文件，用空格分隔，或输入 'list' 查看可用文件")
        
        while True:
            input_str = input("> ").strip()
            if not input_str:
                continue
            
            if input_str.lower() == 'list':
                if os.path.exists(default_dir):
                    available_files = [f for f in os.listdir(default_dir) if f.endswith('.txt')]
                    if available_files:
                        print("可用文件:")
                        for i, f in enumerate(available_files, 1):
                            print(f"  {i}. {f}")
                        print("请输入文件名（用空格分隔可多选）:")
                    else:
                        print("默认目录中没有txt文件")
                continue
            
            # 支持空格分隔的多个文件
            input_files = input_str.split()
            
            for file_path in input_files:
                if os.path.exists(file_path):
                    files.append(file_path)
                else:
                    # 尝试在默认目录中查找
                    full_path = os.path.join(default_dir, file_path)
                    if os.path.exists(full_path):
                        files.append(full_path)
                    else:
                        print(f"警告: 文件不存在，已跳过: {file_path}")
            
            if files:
                break
            else:
                print("没有找到有效文件，请重新输入")
    
    return files


def ensure_http_prefix(server):
    """确保服务器地址有http://前缀"""
    server = server.strip()
    if not server.startswith('http://') and not server.startswith('https://'):
        return f"http://{server}"
    return server


def test_udpxy_server(server, test_url):
    """测试udpxy服务器是否有效"""
    try:
        start_time = time.time()
        with requests.get(test_url, stream=True, timeout=(3, 5)) as resp:
            if resp.status_code == 200:
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                    if downloaded >= 16384:
                        end_time = time.time()
                        speed = end_time - start_time
                        return server, True, speed
                end_time = time.time()
                if downloaded > 0:
                    speed = end_time - start_time
                    return server, True, speed
                return server, False, end_time - start_time
            else:
                return server, False, 9999.0
    except requests.exceptions.ConnectTimeout:
        return server, False, 9999.0
    except requests.exceptions.ConnectionError:
        return server, False, 9999.0
    except Exception as e:
        return server, False, 9999.0


def detect_isp(file_name, dir_name):
    """从文件名或目录名识别运营商"""
    if "移动" in file_name or "移动" in dir_name:
        return "移动"
    elif "联通" in file_name or "联通" in dir_name:
        return "联通"
    return "电信"


def parse_udpxy_file(file_path):
    """
    解析udpxy服务器地址文件
    支持格式：
    1. 5列格式：运营商,省份,城市,服务器地址,标签（标签为空或"有效"表示有效服务器，"无效"表示无效服务器）
    2. 4列格式：运营商,省份,城市,服务器地址
    3. 3列格式：省份,城市,服务器地址，运营商由文件名或目录名关键字识别
    4. 2列格式：省份,服务器地址，运营商由文件名或目录名关键字识别
    """
    regions = {}
    current_region = None
    known_regions = {"江苏", "上海", "浙江", "广东", "北京", "四川", "山东", "福建", 
                     "贵州", "重庆", "青海", "广西", "湖南", "宁夏", "云南", "内蒙", 
                     "天津", "安徽", "山西", "江西", "河北", "河南", "海南", "湖北", 
                     "甘肃", "辽宁", "吉林", "陕西", "黑龙江", "新疆", "台湾", "香港", "澳门"}

    # 从文件名或目录名识别省份和运营商
    file_name = os.path.basename(file_path)
    dir_name = os.path.basename(os.path.dirname(file_path))
    
    detected_region_from_filename = None
    detected_isp = detect_isp(file_name, dir_name)
    
    # 首先从文件名识别
    for region in known_regions:
        if region in file_name:
            detected_region_from_filename = region
            break
    
    # 如果文件名中没有，从目录名识别
    if not detected_region_from_filename:
        for region in known_regions:
            if region in dir_name:
                detected_region_from_filename = region
                break

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith('#'):
                    continue
                if stripped.startswith('省份') or stripped.startswith('运营商'):
                    continue

                parts = stripped.split(',')
                server = ""
                tag = ""
                region_name = ""
                
                # 判断格式：5列格式（运营商,省份,城市,服务器地址,标签）
                if len(parts) >= 5 and parts[3].strip() and ':' in parts[3]:
                    # 5列格式：运营商,省份,城市,服务器地址,标签
                    isp = parts[0].strip()
                    province = parts[1].strip()
                    # 确保省份不为空且是已知省份
                    if province in known_regions:
                        region_name = f"{isp}-{province}"
                        server = parts[3].strip()
                        tag = parts[4].strip() if len(parts) > 4 else ''
                    else:
                        # 如果省份未知，尝试从文件名识别
                        if detected_region_from_filename:
                            region_name = f"{isp}-{detected_region_from_filename}"
                            server = parts[3].strip()
                            tag = parts[4].strip() if len(parts) > 4 else ''
                # 判断格式：4列格式（运营商,省份,城市,服务器地址）
                elif len(parts) >= 4 and parts[3].strip() and ':' in parts[3]:
                    # 4列格式：运营商,省份,城市,服务器地址
                    isp = parts[0].strip()
                    province = parts[1].strip()
                    # 确保省份不为空且是已知省份
                    if province in known_regions:
                        region_name = f"{isp}-{province}"
                        server = parts[3].strip()
                        tag = ''  # 4列格式没有标签列
                    else:
                        # 如果省份未知，尝试从文件名识别
                        if detected_region_from_filename:
                            region_name = f"{isp}-{detected_region_from_filename}"
                            server = parts[3].strip()
                            tag = ''
                elif len(parts) >= 3 and parts[2].strip() and ':' in parts[2]:
                    # 3列格式：省份,城市,服务器地址
                    province = parts[0].strip()
                    # 使用已识别的运营商
                    if province in known_regions:
                        region_name = f"{detected_isp}-{province}"
                        server = parts[2].strip()
                    elif detected_region_from_filename:
                        region_name = f"{detected_isp}-{detected_region_from_filename}"
                        server = parts[2].strip()
                elif len(parts) == 2 and parts[1].strip() and ':' in parts[1]:
                    # 2列格式：省份,服务器地址
                    province = parts[0].strip()
                    # 使用已识别的运营商
                    if province in known_regions:
                        region_name = f"{detected_isp}-{province}"
                        server = parts[1].strip()
                    elif detected_region_from_filename:
                        region_name = f"{detected_isp}-{detected_region_from_filename}"
                        server = parts[1].strip()
                
                if region_name and ':' in server:
                    if region_name not in regions:
                        regions[region_name] = {"active": [], "failed": []}
                    # 根据标签判断是有效还是无效服务器
                    if tag == "无效":
                        regions[region_name]["failed"].append(server)
                    else:
                        regions[region_name]["active"].append(server)
    except Exception as e:
        print(f"解析文件失败: {e}")
        return {}

    return regions


def parse_test_config(file_path):
    """
    解析测试配置文件
    格式：运营商,省份,频道名,组播地址（逗号分隔）
    返回：{省份: 完整测试URL}
    """
    test_urls = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('省份') or line.startswith('运营商'):
                    continue
                parts = line.split(',')
                # 支持4列格式：运营商,省份,频道名,组播地址
                if len(parts) >= 4:
                    isp = parts[0].strip()
                    region = parts[1].strip()
                    channel = parts[2].strip()
                    multicast_addr = parts[3].strip()
                # 兼容旧的3列格式：省份,频道名,组播地址
                elif len(parts) >= 3:
                    region = parts[0].strip()
                    channel = parts[1].strip()
                    multicast_addr = parts[2].strip()
                
                if region and multicast_addr:
                    # 使用"运营商-省份"作为键
                    key = f"{isp}-{region}" if isp else region
                    test_urls[key] = f"{TEST_PROTOCOL}://{multicast_addr}"
                    # 同时也添加省份作为键（向后兼容）
                    if key != region:
                        test_urls[region] = f"{TEST_PROTOCOL}://{multicast_addr}"
    except FileNotFoundError:
        print(f"错误: 测试地址配置文件 {file_path} 不存在")
        return None
    except Exception as e:
        print(f"解析测试地址文件失败: {e}")
        return None
    return test_urls


def extract_region_from_filename(filename):
    """从文件名中提取省份信息和ISP"""
    known_regions = {"江苏", "上海", "浙江", "广东", "北京", "四川", "山东", "福建", 
                     "贵州", "重庆", "青海", "广西", "湖南", "宁夏", "云南", "内蒙", 
                     "天津", "安徽", "山西", "江西", "河北", "河南", "海南", "湖北", 
                     "甘肃", "辽宁", "吉林", "陕西", "黑龙江", "新疆", "台湾", "香港", "澳门"}
    
    region = None
    isp = None
    
    for r in known_regions:
        if r in filename:
            region = r
            break
    
    # 提取ISP
    isp_keywords = {"电信": "电信", "移动": "移动", "联通": "联通"}
    for keyword, value in isp_keywords.items():
        if keyword in filename:
            isp = value
            break
    
    return region, isp


def main():
    global MAX_WORKERS, TEST_PROTOCOL, TEST_INVALID_SERVERS

    # 命令行参数解析
    parser = argparse.ArgumentParser(description='udpxy服务器测试工具')
    parser.add_argument('-p', '--protocol', choices=['rtp', 'udp'], default=TEST_PROTOCOL,
                        help=f'测试协议，可选 rtp 或 udp（默认: {TEST_PROTOCOL}）')
    parser.add_argument('-f', '--file', help='udpxy服务器地址列表文件路径')
    parser.add_argument('-w', '--workers', type=int, default=MAX_WORKERS,
                        help=f'并发测试线程数（默认: {MAX_WORKERS}）')
    parser.add_argument('-a', '--all', action='store_true', help='强制测试所有地址（包括测试失败的地址）')
    parser.add_argument('-t', '--test-invalid', action='store_true', default=TEST_INVALID_SERVERS,
                        help=f'是否测试标记为"无效"的服务器（默认: {TEST_INVALID_SERVERS}）')
    args = parser.parse_args()

    # 设置参数
    TEST_PROTOCOL = args.protocol
    MAX_WORKERS = args.workers
    force_test_all = args.all
    TEST_INVALID_SERVERS = args.test_invalid

    # 测试用组播配置文件
    test_config_file = os.path.normpath("config/test_udpxy_config.txt")
    nodes_file = os.path.normpath("nodes.txt")
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    log_dir = os.path.normpath("log")
    log_file = os.path.normpath(os.path.join(log_dir, f"udpxy_health_check_{timestamp}.log"))

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    print("=" * 80)
    print("udpxy 服务器测试工具")
    print("=" * 80)

    print(f"测试协议: {TEST_PROTOCOL}")
    print(f"并发数: {MAX_WORKERS}")
    print(f"测试无效服务器: {'是' if TEST_INVALID_SERVERS else '否'}")
    if force_test_all:
        print("模式: 强制测试所有地址")
    print("=" * 80)

    # 选择udpxy服务器地址列表文件（支持多选）
    print("\n请选择udpxy服务器地址列表文件（可多选）...")
    udpxy_files = []
    
    if args.file and os.path.exists(args.file):
        udpxy_files.append(args.file)
        print(f"已通过参数指定文件: {args.file}")
    else:
        udpxy_files = select_udpxy_files()
        if not udpxy_files:
            print("未选择文件，退出程序")
            return
        print(f"已选择 {len(udpxy_files)} 个文件:")
        for i, f in enumerate(udpxy_files, 1):
            print(f"  {i}. {os.path.basename(f)}")

    print(f"\n读取测试地址配置文件: {test_config_file}")
    region_test_urls = parse_test_config(test_config_file)
    if region_test_urls is None:
        return

    print(f"已配置 {len(region_test_urls)} 个地区的测试地址")

    import threading
    class Logger:
        def __init__(self, filename):
            self.console = sys.stdout
            self.file = open(filename, 'w', encoding='utf-8')
            self.lock = threading.Lock()

        def write(self, message):
            with self.lock:
                self.console.write(message)
                self.file.write(message)

        def flush(self):
            with self.lock:
                self.console.flush()
                self.file.flush()

        def close(self):
            with self.lock:
                self.file.close()

    sys.stdout = Logger(log_file)

    # 合并多个文件的服务器数据
    regions = {}
    all_files_failed = True
    
    for udpxy_file in udpxy_files:
        print(f"正在解析文件: {os.path.basename(udpxy_file)}")
        file_regions = parse_udpxy_file(udpxy_file)
        if file_regions:
            all_files_failed = False
            # 合并到总的regions中
            for region, data in file_regions.items():
                if region not in regions:
                    regions[region] = {"active": [], "failed": []}
                regions[region]["active"].extend(data["active"])
                regions[region]["failed"].extend(data["failed"])
                # 去重
                regions[region]["active"] = list(set(regions[region]["active"]))
                regions[region]["failed"] = list(set(regions[region]["failed"]))
        else:
            print(f"  警告: 文件 {os.path.basename(udpxy_file)} 没有找到服务器列表")

    if not regions or all_files_failed:
        print("没有找到服务器列表")
        return

    total_active = sum(len(r["active"]) for r in regions.values())
    total_failed = sum(len(r["failed"]) for r in regions.values())

    # 提取运营商信息
    isps = set()
    for region in regions.keys():
        if '-' in region:
            isp = region.split('-')[0]
            isps.add(isp)
        else:
            isps.add("未知")
    
    print(f"\n共发现 {len(isps)} 个运营商的服务器")
    print(f"共发现 {len(regions)} 个地区的服务器")
    print(f"活动服务器: {total_active} 个", end="")
    if total_failed > 0:
        print(f"，前一次测试无效服务器: {total_failed} 个")
    else:
        print()
    if force_test_all:
        print(f"共测试服务器: {total_active + total_failed} 个")
    
    # 并发数不能超过活动服务器数量
    actual_workers = min(MAX_WORKERS, total_active) if total_active > 0 else MAX_WORKERS
    print(f"并发数: {actual_workers}")
    print("=" * 80)

    # 如果没有活动服务器且设置为不测试无效服务器，则直接退出
    if total_active == 0 and not TEST_INVALID_SERVERS and not force_test_all:
        print("\n没有活动服务器需要测试，程序退出")
        sys.stdout = sys.stdout.console
        print(f"没有活动服务器需要测试，详细日志已保存到 {log_file}")
        return

    results = {}
    active_invalid = []
    valid_failed = []
    invalid_failed = []

    for region, servers_data in regions.items():
        servers = servers_data["active"]
        failed = servers_data["failed"] if force_test_all else []

        print(f"\n测试 [{region}] 地区的服务器...")
        print(f"  活动服务器: {len(servers)} 个", end="")
        if force_test_all and failed:
            print(f"，测试失败服务器: {len(failed)} 个")
        else:
            print()

        # 首先尝试完整匹配（运营商-省份）
        if region in region_test_urls:
            test_url_base = region_test_urls[region]
        else:
            # 严格匹配运营商-省份，不回退到省份-only匹配
            print(f"  错误: {region} 没有配置测试地址，跳过该地区")
            continue
        print(f"  测试组播地址: {test_url_base}")

        # 解析组播地址
        match = re.search(r'(rtp|udp)://([\d.]+):(\d+)', test_url_base)
        if not match:
            print(f"  测试地址格式错误: {test_url_base}")
            continue

        protocol, ip, port = match.groups()

        def build_test_url(server):
            # 移除服务器地址中的http://前缀
            server_clean = server.replace('http://', '').replace('https://', '')
            return f"http://{server_clean}/{protocol}/{ip}:{port}"

        # 根据配置决定是否测试失败的服务器
        if TEST_INVALID_SERVERS:
            all_servers = servers + failed
        else:
            all_servers = servers.copy()

        server_speed_map = {}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(test_udpxy_server, server, build_test_url(server)): server for server in all_servers}

            for future in futures:
                server, is_valid, speed = future.result()
                server_speed_map[server] = speed
                if is_valid:
                    print(f"  [√] {server} - 耗时: {speed:.2f}s")
                    if server in failed:
                        valid_failed.append(server)
                else:
                    print(f"  [×] {server} - 无效")
                    if server in failed:
                        invalid_failed.append(server)
                    else:
                        active_invalid.append(server)

        results[region] = {"active": servers, "valid_failed": [s for s in failed if s in valid_failed], "speed_map": server_speed_map}

    print("\n" + "=" * 80)

    # 保存测试结果（包含带前缀和不带前缀两种形式）
    active_invalid_set = set()
    for server in active_invalid:
        active_invalid_set.add(server)
        active_invalid_set.add(ensure_http_prefix(server))
    valid_failed_set = set(valid_failed)
    for server in valid_failed:
        valid_failed_set.add(ensure_http_prefix(server))
    
    # 收集实际参与测试的服务器地址（包含带前缀和不带前缀两种形式）
    tested_servers = set()
    tested_servers_with_prefix = set()
    for region, data in results.items():
        for server in data["active"]:
            tested_servers.add(server)
            tested_servers_with_prefix.add(ensure_http_prefix(server))
        for server in data["valid_failed"]:
            tested_servers.add(server)
            tested_servers_with_prefix.add(ensure_http_prefix(server))
    
    # 测试失败的活动服务器也应该被记录
    for server in active_invalid:
        tested_servers.add(server)
        tested_servers_with_prefix.add(ensure_http_prefix(server))
    
    try:
        # 1. 每个测试文件单独保存一个带health_checked后缀的文件（5列格式）
        print(f"\n保存每个文件的测试结果...")
        for udpxy_file in udpxy_files:
            file_name = os.path.basename(udpxy_file)
            health_checked_filename = f"{os.path.splitext(udpxy_file)[0]}_health_checked.txt"
            
            with open(udpxy_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            marked_lines = []
            has_header = False
            
            for line in lines:
                stripped = line.strip()
                
                if not stripped:
                    marked_lines.append(line)
                    continue
                
                if stripped.startswith('#'):
                    marked_lines.append(line)
                    continue
                # 更新头部行为5列格式
                elif stripped.startswith('省份') or stripped.startswith('运营商'):
                    marked_lines.append("# 运营商,省份,城市,服务器地址,标签\n")
                    has_header = True
                    continue
                elif ',' in stripped:
                    parts = stripped.split(',')
                    
                    if len(parts) >= 4 and ':' in parts[3]:
                        # 4列格式：运营商,省份,城市,服务器地址
                        isp = parts[0].strip()
                        region = parts[1].strip()
                        city = parts[2].strip()
                        server = parts[3].strip()
                        server_with_prefix = ensure_http_prefix(server)
                        tag = ''
                        
                        if server_with_prefix in active_invalid_set:
                            marked_lines.append(f"{isp},{region},{city},{server_with_prefix},无效\n")
                        elif server_with_prefix in tested_servers_with_prefix:
                            marked_lines.append(f"{isp},{region},{city},{server_with_prefix},有效\n")
                        else:
                            marked_lines.append(f"{isp},{region},{city},{server_with_prefix},{tag}\n")
                    elif len(parts) >= 3:
                        # 3列格式：省份,城市,服务器地址
                        region = parts[0]
                        city = parts[1] if len(parts) > 1 else ''
                        server = parts[2].strip()
                        server_with_prefix = ensure_http_prefix(server)
                        # 检查是否有标签列
                        if len(parts) >= 4:
                            tag = parts[3].strip()
                        else:
                            tag = ''
                        
                        # 根据测试结果更新标签
                        if server_with_prefix in active_invalid_set:
                            marked_lines.append(f"{isp},{region},{city},{server_with_prefix},无效\n")
                        elif server_with_prefix in tested_servers_with_prefix:
                            marked_lines.append(f"{isp},{region},{city},{server_with_prefix},有效\n")
                        else:
                            # 未参与测试，保持原标签或空
                            marked_lines.append(f"{isp},{region},{city},{server_with_prefix},{tag}\n")
                    elif len(parts) == 2:
                        region = parts[0]
                        server = parts[1].strip()
                        server_with_prefix = ensure_http_prefix(server)
                        if server_with_prefix in active_invalid_set:
                            marked_lines.append(f"{isp},{region},,{server_with_prefix},无效\n")
                        elif server_with_prefix in tested_servers_with_prefix:
                            marked_lines.append(f"{isp},{region},,{server_with_prefix},有效\n")
                        else:
                            marked_lines.append(f"{isp},{region},,{server_with_prefix},\n")
                    else:
                        marked_lines.append(line)
                elif stripped:
                    if ':' in stripped:
                        server_with_prefix = ensure_http_prefix(stripped.strip())
                        region, _ = extract_region_from_filename(file_name)
                        # 使用detect_isp函数识别运营商
                        isp = detect_isp(file_name, os.path.basename(os.path.dirname(udpxy_file)))
                        if server_with_prefix in active_invalid_set:
                            marked_lines.append(f"{isp},{region},,{server_with_prefix},无效\n")
                        elif server_with_prefix in tested_servers_with_prefix:
                            marked_lines.append(f"{isp},{region},,{server_with_prefix},有效\n")
                        else:
                            marked_lines.append(f"{isp},{region},,{server_with_prefix},\n")
                    else:
                        marked_lines.append(line)
            
            # 如果文件没有头部行，添加一个
            if not has_header and marked_lines:
                # 在第一行非空内容前插入头部行
                marked_lines.insert(0, "# 运营商,省份,城市,服务器地址,标签\n")
            
            with open(health_checked_filename, 'w', encoding='utf-8') as f:
                f.writelines(marked_lines)
            
            print(f"  {os.path.basename(health_checked_filename)}")
        
        # 2. 追加到汇总文件 udpxy_servers_active.txt（3列格式，只记录有效的服务器）
        print(f"\n追加到汇总文件 udpxy_servers_active.txt...")
        
        # 保存到 udpxy_servers 目录
        summary_dir = "udpxy_servers"
        os.makedirs(summary_dir, exist_ok=True)
        active_file = os.path.join(summary_dir, "udpxy_servers_active.txt")
        
        # 读取已有数据进行去重（支持3列格式）
        existing_active = set()
        active_file_exists = os.path.exists(active_file)
        
        if active_file_exists:
            with open(active_file, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue
                    if ',' in stripped:
                        parts = stripped.split(',')
                        if len(parts) >= 3:
                            server = parts[2].strip()
                            existing_active.add(server)
        
        # 收集有效的服务器（3列格式：运营商,省份,服务器地址）
        active_lines = []
        
        for region, data in results.items():
            # 获取有效的服务器列表（排除无效的）
            valid_servers = [s for s in data["active"] if s not in active_invalid]
            valid_servers.extend(data["valid_failed"])
            
            # 从地区推断ISP
            # 从地区名提取ISP和省份（处理"运营商-省份"格式）
            isp = "电信"
            province = region
            if '-' in region:
                parts = region.split('-', 1)
                isp = parts[0]
                province = parts[1]
            
            for server in valid_servers:
                server_with_prefix = ensure_http_prefix(server)
                if server_with_prefix not in existing_active:
                    active_lines.append(f"{isp},{province},{server_with_prefix}\n")
        
        # 写入有效服务器文件
        if active_lines:
            with open(active_file, 'a', encoding='utf-8') as f:
                if not active_file_exists:
                    f.write("# 运营商,省份,服务器地址\n")
                f.writelines(active_lines)
            
            print(f"  已追加 {len(active_lines)} 条数据到 {active_file}")
        else:
            print(f"  没有新数据需要追加")
        
        # 复制 udpxy_servers_active.txt 到 nodes.txt
        print(f"\n复制 {active_file} 到 {nodes_file}...")
        try:
            if os.path.exists(active_file):
                with open(active_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(nodes_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  成功复制到 {nodes_file}")
            else:
                print(f"  源文件 {active_file} 不存在")
        except Exception as e:
            print(f"  复制失败: {e}")
        
        # 3. 汇总到 udpxy_servers_history.txt（追加模式，5列格式，记录所有测试结果）
        print(f"\n追加到汇总文件 udpxy_servers_history.txt...")
        
        history_file = os.path.join(summary_dir, "udpxy_servers_history.txt")
        
        # 读取已有数据进行去重和状态更新（支持5列格式）
        existing_history = {}  # key: server, value: {line, tag}
        history_file_exists = os.path.exists(history_file)
        
        if history_file_exists:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue
                    if ',' in stripped:
                        parts = stripped.split(',')
                        if len(parts) >= 4:
                            server = parts[3].strip()
                            server = ensure_http_prefix(server)
                            tag = parts[4].strip() if len(parts) >= 5 else ''
                            existing_history[server] = {'line': line.rstrip('\n'), 'tag': tag}
        
        # 处理每个文件的测试结果（从health_checked文件读取）
        history_lines = []
        
        for udpxy_file in udpxy_files:
            health_checked_filename = f"{os.path.splitext(udpxy_file)[0]}_health_checked.txt"
            if not os.path.exists(health_checked_filename):
                continue
            
            with open(health_checked_filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                stripped = line.strip()
                
                if not stripped:
                    continue
                if stripped.startswith('#'):
                    continue
                
                if ',' in stripped:
                    parts = stripped.split(',')
                    if len(parts) >= 4:
                        # 5列格式：运营商,省份,城市,服务器地址,标签
                        isp = parts[0]
                        region = parts[1]
                        city = parts[2] if len(parts) > 2 else ''
                        server = ensure_http_prefix(parts[3].strip())
                        current_tag = parts[4].strip() if len(parts) >= 5 else ''
                        
                        # 只处理参与测试的地址
                        if server not in tested_servers_with_prefix:
                            continue
                        
                        if server in existing_history:
                            old_tag = existing_history[server]['tag']
                            if old_tag != current_tag:
                                history_lines.append(f"{isp},{region},{city},{server},{current_tag}\n")
                        else:
                            history_lines.append(f"{isp},{region},{city},{server},{current_tag}\n")
        
        # 写入历史文件
        if history_lines:
            with open(history_file, 'a', encoding='utf-8') as f:
                if not history_file_exists:
                    f.write("# 运营商,省份,城市,服务器地址,标签\n")
                f.writelines(history_lines)
            
            print(f"  已追加 {len(history_lines)} 条数据到 {history_file}")
        else:
            print(f"  没有新数据需要追加")
    except Exception as e:
        print(f"保存测试结果失败: {e}")
        import traceback
        traceback.print_exc()
        return

    total_servers = total_active + total_failed if force_test_all else total_active
    total_valid = sum(len([s for s in data["active"] if s not in active_invalid]) for data in results.values()) + len(valid_failed)
    total_invalid = len(active_invalid) + len(invalid_failed)

    print("=" * 80)
    print(f"测试完成: 有效 {total_valid}, 无效 {total_invalid}, 总计 {total_servers}")
    if force_test_all and valid_failed:
        print(f"有 {len(valid_failed)} 个测试失败的服务器通过测试")
    print("=" * 80)

    sys.stdout = sys.stdout.console
    print(f"测试完成，详细日志已保存到 {log_file}")
    print(f"服务器列表已保存到 udpxy_servers/udpxy_servers_active.txt")
    print(f"测试历史已保存到 udpxy_servers/udpxy_servers_history.txt")


if __name__ == "__main__":
    main()
