import os
import re
import time
import tkinter as tk
from tkinter import filedialog, messagebox

def extract_info(line, current_category="未分类"):
    """
    从一行数据中提取信息
    格式1：频道名,http://udpxy服务器/rtp/组播地址:端口（udpxy模式，2列）
    格式2：频道名,http://udpxy服务器/udp/组播地址:端口（udpxy模式，2列）
    格式3：频道名,rtp://组播地址:端口（纯组播模式，2列）
    格式4：频道名,udp://组播地址:端口（纯组播模式，2列）
    格式5：分类,频道名,http://udpxy服务器/rtp/组播地址:端口（udpxy模式，3列）
    格式6：分类,频道名,http://udpxy服务器/udp/组播地址:端口（udpxy模式，3列）
    格式7：分类,频道名,rtp://组播地址:端口（纯组播模式，3列）
    格式8：分类,频道名,udp://组播地址:端口（纯组播模式，3列）
    格式9：239.x.x.x:port（纯组播地址，无逗号）
    格式10：频道名,http://{{模板变量}}/rtp/组播地址:端口（模板模式）
    格式11：频道名,http://{{模板变量}}/udp/组播地址:端口（模板模式）
    返回：(频道名, udpxy服务器或None或模板变量, 组播地址, 模式, 分类)
    """
    line = line.strip()
    
    # 处理纯组播地址（无逗号，239开头）
    if ',' not in line:
        if line.startswith('rtp://'):
            match = re.match(r'rtp://([^:]+:\d+)', line)
            if match:
                return None, None, match.group(1), 'multicast', current_category
        elif line.startswith('udp://'):
            match = re.match(r'udp://([^:]+:\d+)', line)
            if match:
                return None, None, match.group(1), 'multicast', current_category
        elif line.count('.') >= 3 and ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2 and parts[0].split('.')[0] == '239':
                return None, None, line, 'multicast', current_category
        return None, None, None, None, current_category
    
    parts = line.split(',', 2)
    
    if len(parts) == 2:
        # 2列格式：频道名,地址
        channel_name = parts[0].strip()
        url = parts[1].strip()
        
        # 尝试 udpxy 模式（包括模板变量格式）：http://udpxy服务器/rtp/组播地址:端口
        match = re.match(r'http://([^/]+)/(?:rtp|udp)/([^:]+:\d+)', url)
        if match:
            udpxy_server = match.group(1)
            # 检测是否为模板变量
            if udpxy_server.startswith('{{') and udpxy_server.endswith('}}'):
                return channel_name, udpxy_server, match.group(2), 'template', current_category
            return channel_name, udpxy_server, match.group(2), 'udpxy', current_category
        
        # 尝试纯组播模式：rtp://组播地址:端口 或 udp://组播地址:端口
        match = re.match(r'(?:rtp|udp)://([^:]+:\d+)', url)
        if match:
            return channel_name, None, match.group(1), 'multicast', current_category
        
        # 尝试纯IP地址格式：239.x.x.x:port
        if url.count('.') >= 3 and ':' in url:
            ip_parts = url.split(':')[0].split('.')
            if len(ip_parts) == 4 and ip_parts[0] == '239':
                return channel_name, None, url, 'multicast', current_category
        
    elif len(parts) == 3:
        # 3列格式：分类,频道名,地址
        category = parts[0].strip() or current_category
        channel_name = parts[1].strip()
        url = parts[2].strip()
        
        # 尝试 udpxy 模式（包括模板变量格式）
        match = re.match(r'http://([^/]+)/(?:rtp|udp)/([^:]+:\d+)', url)
        if match:
            udpxy_server = match.group(1)
            # 检测是否为模板变量
            if udpxy_server.startswith('{{') and udpxy_server.endswith('}}'):
                return channel_name, udpxy_server, match.group(2), 'template', category
            return channel_name, udpxy_server, match.group(2), 'udpxy', category
        
        # 尝试纯组播模式
        match = re.match(r'(?:rtp|udp)://([^:]+:\d+)', url)
        if match:
            return channel_name, None, match.group(1), 'multicast', category
        
        # 尝试纯IP地址格式
        if url.count('.') >= 3 and ':' in url:
            ip_parts = url.split(':')[0].split('.')
            if len(ip_parts) == 4 and ip_parts[0] == '239':
                return channel_name, None, url, 'multicast', category
    
    return None, None, None, None, current_category

def extract_info_from_m3u(extinf_line, url_line):
    """
    从 M3U 格式中提取信息
    extinf_line: #EXTINF:-1 group-title="分类",频道名
    url_line: http://udpxy服务器/rtp/组播地址:端口 或 http://udpxy服务器/udp/组播地址:端口 或 rtp://组播地址:端口 或 udp://组播地址:端口
    返回：(频道名, udpxy服务器或None, 组播地址, 模式, 分类)
    """
    # 提取分类
    category = "未分类"
    match = re.search(r'group-title="([^"]+)"', extinf_line)
    if match:
        category = match.group(1)
    
    # 提取频道名（找到最后一个逗号，忽略前面的属性）
    channel_name = None
    last_comma_index = extinf_line.rfind(',')
    if last_comma_index != -1:
        channel_name = extinf_line[last_comma_index + 1:].strip()
    
    if not channel_name:
        return None, None, None, None, category
    
    # 提取地址信息
    url = url_line.strip()
    
    # 尝试 udpxy 模式（包括模板变量格式）
    match = re.match(r'http://([^/]+)/(?:rtp|udp)/([^:]+:\d+)', url)
    if match:
        udpxy_server = match.group(1)
        multicast_addr = match.group(2)
        # 检测是否为模板变量
        if udpxy_server.startswith('{{') and udpxy_server.endswith('}}'):
            return channel_name, udpxy_server, multicast_addr, 'template', category
        return channel_name, udpxy_server, multicast_addr, 'udpxy', category
    
    # 尝试纯组播模式（支持 rtp://、rtp:///、udp://、udp:/// 格式）
    match = re.match(r'(?:rtp|udp)://*/?([^:]+:\d+)', url)
    if match:
        multicast_addr = match.group(1)
        return channel_name, None, multicast_addr, 'multicast', category
    
    # 尝试无协议前缀格式：233.x.x.x:port
    match = re.match(r'^(233\.\d+\.\d+\.\d+:\d+)$', url)
    if match:
        multicast_addr = match.group(1)
        return channel_name, None, multicast_addr, 'multicast', category
    
    return channel_name, None, None, None, category

def normalize_path(path):
    """将路径中的反斜杠替换为正斜杠"""
    return path.replace('\\', '/')

def extract_region(file_path):
    """从文件名或目录名提取地区和ISP，支持当前目录和上一级目录"""
    known_regions = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
                     "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                     "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
                     "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]
    
    region = None
    isp = None
    
    # 从文件名提取
    file_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(file_name)[0]
    
    for r in known_regions:
        if r in name_without_ext:
            region = r
            break
    
    # 提取ISP
    isp_keywords = {"电信": "电信", "移动": "移动", "联通": "联通"}
    for keyword, value in isp_keywords.items():
        if keyword in name_without_ext:
            isp = value
            break
    
    # 如果文件名中没有，从当前目录名提取
    if not region or not isp:
        dir_name = os.path.basename(os.path.dirname(file_path))
        
        if not region:
            for r in known_regions:
                if r in dir_name:
                    region = r
                    break
        
        if not isp:
            for keyword, value in isp_keywords.items():
                if keyword in dir_name:
                    isp = value
                    break
    
    # 如果当前目录也没有，从上一级目录提取
    if not region or not isp:
        parent_dir_name = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
        
        if not region:
            for r in known_regions:
                if r in parent_dir_name:
                    region = r
                    break
        
        if not isp:
            for keyword, value in isp_keywords.items():
                if keyword in parent_dir_name:
                    isp = value
                    break
    
    return region, isp

def process_file(file_path, channels, servers, current_category):
    """
    处理单个文件
    返回：(当前分类, 是否检测到udpxy模式, 是否检测到纯组播模式, 读取频道数, 读取服务器数, 新增频道数, 新增服务器数)
    channels 字典结构：{multicast_addr: (category, channel_name)}
    """
    has_udpxy = False
    has_multicast = False
    read_channels = 0
    read_servers_set = set()
    added_channels = 0
    added_servers = 0
    
    # 检测是否为 m3u 文件
    is_m3u = file_path.lower().endswith('.m3u')
    
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines_processed = 0
            lines_valid = 0
            
            if is_m3u:
                # 处理 m3u 格式
                extinf_line = None
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    lines_processed += 1
                    
                    if not line:
                        continue
                    
                    if line.startswith('#EXTINF:'):
                        extinf_line = line
                    elif line and not line.startswith('#') and extinf_line:
                        channel_name, udpxy_server, multicast_addr, mode, category = extract_info_from_m3u(extinf_line, line)
                        if multicast_addr:
                            lines_valid += 1
                            current_category = category
                            
                            read_channels += 1
                            if mode == 'udpxy':
                                has_udpxy = True
                                if udpxy_server:
                                    read_servers_set.add(udpxy_server)
                                # 分类更新优先级规则
                                if multicast_addr in channels:
                                    existing_category, existing_name = channels[multicast_addr]
                                    if category != "未分类" or existing_category == "未分类":
                                        channels[multicast_addr] = (category, channel_name or existing_name)
                                else:
                                    channels[multicast_addr] = (category, channel_name)
                                    added_channels += 1
                                if udpxy_server and udpxy_server not in servers:
                                    servers.add(udpxy_server)
                                    added_servers += 1
                            elif mode == 'template':
                                has_udpxy = True
                                # 模板模式：保存频道信息，但不添加服务器
                                if multicast_addr in channels:
                                    existing_category, existing_name = channels[multicast_addr]
                                    if category != "未分类" or existing_category == "未分类":
                                        channels[multicast_addr] = (category, channel_name or existing_name)
                                else:
                                    channels[multicast_addr] = (category, channel_name)
                                    added_channels += 1
                                # 模板变量不添加到服务器列表
                            else:
                                has_multicast = True
                                if multicast_addr in channels:
                                    existing_category, existing_name = channels[multicast_addr]
                                    if category != "未分类" or existing_category == "未分类":
                                        channels[multicast_addr] = (category, channel_name or existing_name)
                                else:
                                    channels[multicast_addr] = (category, channel_name)
                                    added_channels += 1
                        extinf_line = None
                    elif line.startswith('#'):
                        continue
            else:
                # 处理 txt 格式
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    lines_processed += 1
                    
                    if not line:
                        continue
                    
                    if '#genre#' in line:
                        new_category = line.split(',')[0].strip()
                        current_category = new_category
                    else:
                        channel_name, udpxy_server, multicast_addr, mode, category = extract_info(line, current_category)
                        if multicast_addr:
                            lines_valid += 1
                            read_channels += 1
                            # 使用提取的分类，如果没有则使用当前分类
                            use_category = category if category else current_category
                            
                            if mode == 'udpxy':
                                has_udpxy = True
                                if udpxy_server:
                                    read_servers_set.add(udpxy_server)
                                # 分类更新优先级规则
                                if multicast_addr in channels:
                                    existing_category, existing_name = channels[multicast_addr]
                                    if use_category != "未分类" or existing_category == "未分类":
                                        channels[multicast_addr] = (use_category, channel_name or existing_name)
                                else:
                                    channels[multicast_addr] = (use_category, channel_name)
                                    added_channels += 1
                                if udpxy_server and udpxy_server not in servers:
                                    servers.add(udpxy_server)
                                    added_servers += 1
                            elif mode == 'template':
                                has_udpxy = True
                                # 模板模式：保存频道信息，但不添加服务器
                                if multicast_addr in channels:
                                    existing_category, existing_name = channels[multicast_addr]
                                    if use_category != "未分类" or existing_category == "未分类":
                                        channels[multicast_addr] = (use_category, channel_name or existing_name)
                                else:
                                    channels[multicast_addr] = (use_category, channel_name)
                                    added_channels += 1
                                # 模板变量不添加到服务器列表
                            else:
                                has_multicast = True
                                # 分类更新优先级规则
                                if multicast_addr in channels:
                                    existing_category, existing_name = channels[multicast_addr]
                                    if use_category != "未分类" or existing_category == "未分类":
                                        channels[multicast_addr] = (use_category, channel_name or existing_name)
                                else:
                                    channels[multicast_addr] = (use_category, channel_name)
                                    added_channels += 1
            


            read_servers = len(read_servers_set)
            return current_category, has_udpxy, has_multicast, read_channels, read_servers, added_channels, added_servers
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {e}")
        return current_category, False, False, 0, 0, 0, 0

def select_files():
    """
    选择文件和目录
    """
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    default_dir = os.path.join('playlists', 'collected')
    
    # 选择多个文件
    files = filedialog.askopenfilenames(
        title="选择列表文件",
        initialdir=default_dir,
        filetypes=[("列表文件", "*.txt *.m3u"), ("文本文件", "*.txt"), ("M3U文件", "*.m3u"), ("所有文件", "*.*")]
    )
    
    return files

def get_region_isp_for_file(file_path):
    """
    判断文件是否有地区/运营商信息，返回(地区, 运营商, 是否从文件名提取)
    """
    region, isp = extract_region(file_path)
    
    # 检查文件名是否包含地区/运营商信息
    file_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(file_name)[0]
    
    has_region_in_name = False
    has_isp_in_name = False
    
    known_regions = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
                     "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                     "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
                     "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]
    isp_keywords = {"电信", "移动", "联通"}
    
    for r in known_regions:
        if r in name_without_ext:
            has_region_in_name = True
            break
    
    for keyword in isp_keywords:
        if keyword in name_without_ext:
            has_isp_in_name = True
            break
    
    # 如果文件名中没有地区或运营商信息，从当前目录名提取
    if not has_region_in_name or not has_isp_in_name:
        dir_name = os.path.basename(os.path.dirname(file_path))
        if not has_region_in_name:
            for r in known_regions:
                if r in dir_name:
                    region = r
                    has_region_in_name = True
                    break
        if not has_isp_in_name:
            for keyword in isp_keywords:
                if keyword in dir_name:
                    isp = keyword
                    has_isp_in_name = True
                    break
    
    # 如果当前目录也没有，从上一级目录提取
    if not has_region_in_name or not has_isp_in_name:
        parent_dir_name = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
        if not has_region_in_name:
            for r in known_regions:
                if r in parent_dir_name:
                    region = r
                    has_region_in_name = True
                    break
        if not has_isp_in_name:
            for keyword in isp_keywords:
                if keyword in parent_dir_name:
                    isp = keyword
                    has_isp_in_name = True
                    break
    
    # 默认运营商为电信
    if not isp:
        isp = "电信"
    
    # 判断是否从文件名提取（文件名包含地区和运营商）
    from_filename = has_region_in_name and has_isp_in_name
    
    return region, isp, from_filename

def main():
    """
    主函数
    """
    # 选择文件
    files = select_files()
    if not files:
        print("未选择文件")
        return
    
    # 获取所有文件所在的公共目录
    common_dir = os.path.dirname(files[0])
    # 检查是否所有文件都在同一个目录下
    all_same_dir = all(os.path.dirname(f) == common_dir for f in files)
    
    if not all_same_dir:
        print("警告: 选择的文件不在同一个目录下，将使用第一个文件的目录")
    
    # 获取当前时间
    current_time = time.strftime('%Y/%m/%d %H:%M')
    
    # 定义输出目录
    multicast_output_dir = os.path.normpath(os.path.join('multicast_addresses', 'extracted'))
    udpxy_output_dir = os.path.normpath(os.path.join('udpxy_servers', 'extracted'))
    
    # 确保目录存在
    os.makedirs(multicast_output_dir, exist_ok=True)
    os.makedirs(udpxy_output_dir, exist_ok=True)
    
    # 检查所有文件是否需要单独处理
    files_with_region = []
    has_files_with_name_info = False
    
    for file_path in files:
        region, isp, from_filename = get_region_isp_for_file(file_path)
        files_with_region.append({
            'path': file_path,
            'region': region,
            'isp': isp,
            'from_filename': from_filename
        })
        if from_filename:
            has_files_with_name_info = True
    
    # 根据情况决定处理方式
    if has_files_with_name_info:
        # 有文件名包含地区/运营商信息，每个文件单独处理
        print("检测到文件名包含地区/运营商信息，将分别处理每个文件")
        
        for file_info in files_with_region:
            file_path = file_info['path']
            region = file_info['region']
            isp = file_info['isp']
            
            print(f"\n处理文件: {normalize_path(file_path)}")
            print(f"  提取地区: {region}, 运营商: {isp}")
            
            # 读取已有数据
            channels = {}
            servers = set()
            existing_channels_count = 0
            existing_servers_count = 0
            
            multicast_filename = f'{region}_{isp}_extracted_multicast_addresses.txt'
            udpxy_filename = f'{region}_{isp}_extracted_udpxy_servers.txt'
            
            existing_multicast_file = os.path.normpath(os.path.join(multicast_output_dir, multicast_filename))
            existing_udpxy_file = os.path.normpath(os.path.join(udpxy_output_dir, udpxy_filename))
            
            if os.path.exists(existing_multicast_file):
                with open(existing_multicast_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and ',' in line and not line.startswith('#'):
                            parts = line.split(',', 2)
                            if len(parts) >= 3:
                                category = parts[0].strip()
                                channel_name = parts[1].strip()
                                multicast_addr = parts[2].strip()
                                channels[multicast_addr] = (category, channel_name)
                existing_channels_count = len(channels)
            
            if os.path.exists(existing_udpxy_file):
                with open(existing_udpxy_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # 移除 http:// 前缀，保持与新提取服务器格式一致
                            server = line.replace('http://', '').replace('https://', '')
                            servers.add(server)
                existing_servers_count = len(servers)
            
            # 处理当前文件
            current_category = "未分类"
            current_category, has_udpxy, has_multicast, read_channels, read_servers, added_channels, added_servers = process_file(file_path, channels, servers, current_category)
            
            # 计算新增数量
            new_channels = len(channels) - existing_channels_count
            new_servers = len(servers) - existing_servers_count
            
            # 写入输出文件
            if channels:
                multicast_file = os.path.normpath(os.path.join(multicast_output_dir, multicast_filename))
                with open(multicast_file, 'w', encoding='utf-8') as f:
                    f.write(f"# {current_time}\n")
                    for multicast_addr in sorted(channels.keys()):
                        category, channel_name = channels[multicast_addr]
                        f.write(f"{category},{channel_name},{multicast_addr}\n")
                print(f"  写入组播地址文件: {normalize_path(multicast_file)}")
            
            if servers:
                udpxy_file = os.path.normpath(os.path.join(udpxy_output_dir, udpxy_filename))
                with open(udpxy_file, 'w', encoding='utf-8') as f:
                    f.write(f"# {current_time}\n")
                    for server in sorted(servers):
                        f.write(f"http://{server}\n")
                print(f"  写入服务器文件: {normalize_path(udpxy_file)}")
            
            print(f"  本次读取: {read_channels} 个频道, {read_servers} 个服务器")
            print(f"  新增: {new_channels} 个频道, {new_servers} 个服务器")

    else:
        # 所有文件都没有在文件名中包含地区/运营商信息，统一从目录提取并合并处理
        region, isp = files_with_region[0]['region'], files_with_region[0]['isp']
        print(f"文件名未包含地区/运营商信息，从目录提取: {region}-{isp}")
        print("\n合并处理所有文件:")
        
        # 读取已有数据
        channels = {}
        servers = set()
        
        multicast_filename = f'{region}_{isp}_extracted_multicast_addresses.txt'
        udpxy_filename = f'{region}_{isp}_extracted_udpxy_servers.txt'
        
        existing_multicast_file = os.path.normpath(os.path.join(multicast_output_dir, multicast_filename))
        existing_udpxy_file = os.path.normpath(os.path.join(udpxy_output_dir, udpxy_filename))
        
        if os.path.exists(existing_multicast_file):
            with open(existing_multicast_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ',' in line and not line.startswith('#'):
                        parts = line.split(',', 2)
                        if len(parts) >= 3:
                            category = parts[0].strip()
                            channel_name = parts[1].strip()
                            multicast_addr = parts[2].strip()
                            channels[multicast_addr] = (category, channel_name)
        
        if os.path.exists(existing_udpxy_file):
            with open(existing_udpxy_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # 移除 http:// 前缀，保持与新提取服务器格式一致
                        server = line.replace('http://', '').replace('https://', '')
                        servers.add(server)
        
        # 处理所有文件
        current_category = "未分类"
        total_read_channels = 0
        total_read_servers = 0
        existing_channels_count = len(channels)
        existing_servers_count = len(servers)
        
        for file_info in files_with_region:
            file_path = file_info['path']
            print(f"  - {normalize_path(file_path)}")
            current_category, has_udpxy, has_multicast, read_channels, read_servers, added_channels, added_servers = process_file(file_path, channels, servers, current_category)
            total_read_channels += read_channels
            total_read_servers += read_servers
        
        # 写入输出文件
        if channels:
            multicast_file = os.path.normpath(os.path.join(multicast_output_dir, multicast_filename))
            with open(multicast_file, 'w', encoding='utf-8') as f:
                f.write(f"# {current_time}\n")
                for multicast_addr in sorted(channels.keys()):
                    category, channel_name = channels[multicast_addr]
                    f.write(f"{category},{channel_name},{multicast_addr}\n")
            print(f"\n写入组播地址文件: {normalize_path(multicast_file)}")
        
        if servers:
            udpxy_file = os.path.normpath(os.path.join(udpxy_output_dir, udpxy_filename))
            with open(udpxy_file, 'w', encoding='utf-8') as f:
                f.write(f"# {current_time}\n")
                for server in sorted(servers):
                    f.write(f"http://{server}\n")
            print(f"写入服务器文件: {normalize_path(udpxy_file)}")
        
        new_channels = len(channels) - existing_channels_count
        new_servers = len(servers) - existing_servers_count
        print(f"\n本次读取: {total_read_channels} 个频道, {total_read_servers} 个服务器")
        print(f"新增: {new_channels} 个频道, {new_servers} 个服务器")
        print(f"共有数据: {len(channels)} 个频道, {len(servers)} 个服务器")
    
if __name__ == "__main__":
    main()